from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingestion.common import (
    finish_ingestion_run,
    load_structured_payload,
    normalize_symbol,
    parse_date,
    parse_float,
    parse_int,
    resolve_raw_data_path,
    start_ingestion_run,
)
from app.models.daily_bar import DailyBar
from app.models.institutional_flow import InstitutionalFlow
from app.models.instrument import Instrument


FIELD_ALIASES = {
    "symbol": ["symbol", "ticker"],
    "flow_date": ["flow_date", "date", "trade_date"],
    "fii_net_value": ["fii_net_value", "fii_net", "fii_value", "fii_net_cr"],
    "dii_net_value": ["dii_net_value", "dii_net", "dii_value", "dii_net_cr"],
    "delivery_pct": ["delivery_pct", "delivery_percent", "delivery_percentage"],
    "bulk_deal_count": ["bulk_deal_count", "bulk_deals", "block_deal_count"],
}


def ingest_institutional_flows(
    db: Session,
    *,
    flow_date: date | None = None,
    source_file: str,
    dry_run: bool = False,
) -> Any:
    run, started_at = start_ingestion_run(db, source="manual_file", dataset="institutional_flows")
    notes: list[str] = []
    processed = inserted = updated = 0
    status = "completed"

    try:
        path = Path(source_file)
        if not path.is_absolute():
            path = resolve_raw_data_path("institutional_flows", source_file)
        payload = load_structured_payload(path)
        records = payload if isinstance(payload, list) else payload.get("records", [])

        for raw_record in records:
            symbol = normalize_symbol(_field(raw_record, "symbol"))
            record_date = parse_date(_field(raw_record, "flow_date") or flow_date)
            if not symbol or record_date is None:
                continue

            fii_net_value = parse_float(_field(raw_record, "fii_net_value"))
            dii_net_value = parse_float(_field(raw_record, "dii_net_value"))
            delivery_pct = parse_float(_field(raw_record, "delivery_pct"))
            bulk_deal_count = parse_int(_field(raw_record, "bulk_deal_count"))

            if delivery_pct is None:
                delivery_pct = _lookup_delivery_pct(db, symbol=symbol, flow_date=record_date)

            record = db.get(InstitutionalFlow, {"symbol": symbol, "flow_date": record_date})
            is_new = record is None
            if record is None:
                record = InstitutionalFlow(symbol=symbol, flow_date=record_date)

            record.fii_net_value = fii_net_value
            record.dii_net_value = dii_net_value
            record.delivery_pct = delivery_pct
            record.bulk_deal_count = bulk_deal_count
            record.source = path.name
            db.add(record)

            processed += 1
            inserted += 1 if is_new else 0
            updated += 0 if is_new else 1

        notes.append(f"Institutional flows ingested from {path.name}.")
    except Exception as exc:  # noqa: BLE001
        status = "failed"
        notes.append(f"Institutional flow ingestion failed: {exc}")

    return finish_ingestion_run(
        db,
        run=run,
        started_at=started_at,
        source="manual_file",
        dataset="institutional_flows",
        status=status,
        processed=processed,
        inserted=inserted,
        updated=updated,
        notes=notes,
        dry_run=dry_run,
    )


def _lookup_delivery_pct(db: Session, *, symbol: str, flow_date: date) -> float | None:
    value = db.execute(
        select(DailyBar.deliverable_pct)
        .join(Instrument, DailyBar.instrument_id == Instrument.id)
        .where(Instrument.symbol == symbol, DailyBar.trade_date == flow_date)
    ).scalar_one_or_none()
    return float(value) if value is not None else None


def _field(record: dict[str, Any], name: str) -> Any:
    aliases = FIELD_ALIASES[name]
    for alias in aliases:
        if alias in record:
            return record[alias]
        upper_alias = alias.upper()
        if upper_alias in record:
            return record[upper_alias]
    return None
