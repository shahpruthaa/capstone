from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.ingestion.common import (
    finish_ingestion_run,
    load_structured_payload,
    normalize_symbol,
    parse_date,
    parse_float,
    resolve_raw_data_path,
    start_ingestion_run,
)
from app.models.fundamental_snapshot import FundamentalSnapshot


FIELD_ALIASES = {
    "symbol": ["symbol", "ticker"],
    "quarter_end": ["quarter_end", "quarter", "report_date"],
    "pe_ratio": ["pe_ratio", "pe", "price_to_earnings"],
    "pb_ratio": ["pb_ratio", "pb", "price_to_book"],
    "market_cap": ["market_cap", "market_cap_cr", "market_capitalization"],
    "roe": ["roe", "return_on_equity"],
    "debt_to_equity": ["debt_to_equity", "de_ratio"],
    "current_ratio": ["current_ratio"],
    "revenue_growth_yoy": ["revenue_growth_yoy", "sales_growth_yoy"],
    "profit_growth_yoy": ["profit_growth_yoy", "pat_growth_yoy", "earnings_growth_yoy"],
    "next_earnings_date": ["next_earnings_date", "earnings_date"],
    "earnings_surprise_last": ["earnings_surprise_last", "last_earnings_surprise"],
    "revenue_current": ["revenue", "revenue_current", "sales_current"],
    "revenue_prior": ["revenue_prior", "sales_prior"],
    "profit_current": ["profit", "profit_current", "pat_current"],
    "profit_prior": ["profit_prior", "pat_prior"],
}


def ingest_fundamental_snapshots(
    db: Session,
    *,
    quarter_end: date | None = None,
    source_file: str,
    dry_run: bool = False,
) -> Any:
    run, started_at = start_ingestion_run(db, source="manual_file", dataset="fundamental_snapshots")
    notes: list[str] = []
    processed = inserted = updated = 0
    status = "completed"

    try:
        path = Path(source_file)
        if not path.is_absolute():
            path = resolve_raw_data_path("fundamentals", source_file)
        payload = load_structured_payload(path)
        records = payload if isinstance(payload, list) else payload.get("records", [])

        for raw_record in records:
            symbol = normalize_symbol(_field(raw_record, "symbol"))
            record_quarter = parse_date(_field(raw_record, "quarter_end") or quarter_end)
            if not symbol or record_quarter is None:
                continue

            revenue_growth = parse_float(_field(raw_record, "revenue_growth_yoy"))
            profit_growth = parse_float(_field(raw_record, "profit_growth_yoy"))
            if revenue_growth is None:
                revenue_growth = _growth_yoy(_field(raw_record, "revenue_current"), _field(raw_record, "revenue_prior"))
            if profit_growth is None:
                profit_growth = _growth_yoy(_field(raw_record, "profit_current"), _field(raw_record, "profit_prior"))

            record = db.get(FundamentalSnapshot, {"symbol": symbol, "quarter_end": record_quarter})
            is_new = record is None
            if record is None:
                record = FundamentalSnapshot(symbol=symbol, quarter_end=record_quarter)

            record.pe_ratio = parse_float(_field(raw_record, "pe_ratio"))
            record.pb_ratio = parse_float(_field(raw_record, "pb_ratio"))
            record.market_cap = parse_float(_field(raw_record, "market_cap"))
            record.roe = parse_float(_field(raw_record, "roe"))
            record.debt_to_equity = parse_float(_field(raw_record, "debt_to_equity"))
            record.current_ratio = parse_float(_field(raw_record, "current_ratio"))
            record.revenue_growth_yoy = revenue_growth
            record.profit_growth_yoy = profit_growth
            record.next_earnings_date = parse_date(_field(raw_record, "next_earnings_date"))
            record.earnings_surprise_last = parse_float(_field(raw_record, "earnings_surprise_last"))
            record.source = path.name
            db.add(record)

            processed += 1
            inserted += 1 if is_new else 0
            updated += 0 if is_new else 1

        notes.append(f"Fundamental snapshots ingested from {path.name}.")
    except Exception as exc:  # noqa: BLE001
        status = "failed"
        notes.append(f"Fundamental snapshot ingestion failed: {exc}")

    return finish_ingestion_run(
        db,
        run=run,
        started_at=started_at,
        source="manual_file",
        dataset="fundamental_snapshots",
        status=status,
        processed=processed,
        inserted=inserted,
        updated=updated,
        notes=notes,
        dry_run=dry_run,
    )


def _field(record: dict[str, Any], name: str) -> Any:
    aliases = FIELD_ALIASES[name]
    for alias in aliases:
        if alias in record:
            return record[alias]
        upper_alias = alias.upper()
        if upper_alias in record:
            return record[upper_alias]
    return None


def _growth_yoy(current_value: Any, prior_value: Any) -> float | None:
    current = parse_float(current_value)
    prior = parse_float(prior_value)
    if current is None or prior is None or prior == 0:
        return None
    return round(((current - prior) / abs(prior)) * 100.0, 2)
