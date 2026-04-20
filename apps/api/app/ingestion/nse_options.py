from __future__ import annotations

from datetime import date
from pathlib import Path
from statistics import mean
from typing import Any
from urllib.parse import quote_plus

import requests
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.ingestion.common import (
    COMMON_REQUEST_HEADERS,
    finish_ingestion_run,
    load_structured_payload,
    normalize_symbol,
    parse_date,
    parse_float,
    resolve_raw_data_path,
    start_ingestion_run,
)
from app.models.options_snapshot import OptionsSnapshot


def fetch_nse_options_chain(symbol: str, expiry: date | None = None) -> dict[str, Any]:
    symbol = normalize_symbol(symbol)
    session = requests.Session()
    session.headers.update(COMMON_REQUEST_HEADERS)
    session.get("https://www.nseindia.com/option-chain", timeout=30)

    endpoint = "https://www.nseindia.com/api/option-chain-indices" if symbol in {"NIFTY", "BANKNIFTY", "FINNIFTY"} else "https://www.nseindia.com/api/option-chain-equities"
    response = session.get(f"{endpoint}?symbol={quote_plus(symbol)}", timeout=30)
    response.raise_for_status()
    payload = response.json()
    if expiry is None:
        return payload

    filtered_rows = []
    for row in payload.get("records", {}).get("data", []):
        expiry_text = row.get("expiryDate")
        if expiry_text:
            try:
                row_expiry = parse_date(expiry_text)
            except ValueError:
                row_expiry = None
            if row_expiry == expiry:
                filtered_rows.append(row)

    payload = dict(payload)
    payload["records"] = dict(payload.get("records", {}))
    payload["records"]["data"] = filtered_rows
    return payload


def calculate_pcr(options_data: dict[str, Any]) -> float | None:
    totals = _aggregate_options(options_data)
    call_oi = totals["call_oi"]
    put_oi = totals["put_oi"]
    if call_oi <= 0:
        return None
    return round(put_oi / call_oi, 4)


def calculate_max_pain(options_data: dict[str, Any]) -> float | None:
    strikes: list[tuple[float, float, float]] = []
    for row in _option_rows(options_data):
        strike = parse_float(row.get("strikePrice"))
        if strike is None:
            continue
        call_oi = parse_float((row.get("CE") or {}).get("openInterest")) or 0.0
        put_oi = parse_float((row.get("PE") or {}).get("openInterest")) or 0.0
        strikes.append((strike, call_oi, put_oi))

    if not strikes:
        return None

    best_strike = None
    best_pain = None
    for settlement, _, _ in strikes:
        total_pain = 0.0
        for strike, call_oi, put_oi in strikes:
            total_pain += max(0.0, settlement - strike) * call_oi
            total_pain += max(0.0, strike - settlement) * put_oi
        if best_pain is None or total_pain < best_pain:
            best_pain = total_pain
            best_strike = settlement
    return round(best_strike, 2) if best_strike is not None else None


def detect_unusual_oi(options_data: dict[str, Any], historical_avg: float) -> bool:
    totals = _aggregate_options(options_data)
    current_change = abs(totals["call_oi_change"]) + abs(totals["put_oi_change"])
    if historical_avg <= 0:
        return current_change > 0
    return current_change > (2.0 * historical_avg)


def ingest_options_snapshot(
    db: Session,
    *,
    symbol: str,
    snapshot_date: date,
    expiry_date: date | None = None,
    source_file: str | None = None,
    dry_run: bool = False,
) -> Any:
    run, started_at = start_ingestion_run(db, source="nse", dataset="options_snapshots")
    notes: list[str] = []
    processed = inserted = updated = 0
    status = "completed"

    try:
        source_label = "nse_options_api"
        if source_file:
            payload = _load_options_payload_from_file(source_file)
            source_label = Path(source_file).name
        else:
            payload = fetch_nse_options_chain(symbol=symbol, expiry=expiry_date)

        normalized_symbol = normalize_symbol(symbol)
        totals = _aggregate_options(payload)
        current_iv = totals["avg_iv"]

        historical_iv = db.execute(
            select(OptionsSnapshot.avg_implied_volatility)
            .where(OptionsSnapshot.symbol == normalized_symbol, OptionsSnapshot.avg_implied_volatility.is_not(None))
            .order_by(desc(OptionsSnapshot.snapshot_date))
            .limit(90)
        ).scalars().all()
        iv_percentile = _calculate_iv_percentile(current_iv, [float(value) for value in historical_iv if value is not None])

        historical_oi_changes = db.execute(
            select(OptionsSnapshot.call_oi_change_pct, OptionsSnapshot.put_oi_change_pct)
            .where(OptionsSnapshot.symbol == normalized_symbol)
            .order_by(desc(OptionsSnapshot.snapshot_date))
            .limit(20)
        ).all()
        historical_avg = mean(
            abs(float(call_change or 0.0)) + abs(float(put_change or 0.0))
            for call_change, put_change in historical_oi_changes
        ) if historical_oi_changes else 0.0

        record = db.get(OptionsSnapshot, {"symbol": normalized_symbol, "snapshot_date": snapshot_date})
        is_new = record is None
        if record is None:
            record = OptionsSnapshot(symbol=normalized_symbol, snapshot_date=snapshot_date)

        record.expiry_date = expiry_date or _first_expiry(payload)
        record.pcr_ratio = calculate_pcr(payload)
        record.iv_percentile = iv_percentile
        record.max_pain = calculate_max_pain(payload)
        record.call_oi_change_pct = totals["call_oi_change"]
        record.put_oi_change_pct = totals["put_oi_change"]
        record.unusual_activity = detect_unusual_oi(payload, historical_avg)
        record.avg_implied_volatility = current_iv
        record.total_call_oi = totals["call_oi"]
        record.total_put_oi = totals["put_oi"]
        record.source = source_label

        db.add(record)
        processed = 1
        inserted = 1 if is_new else 0
        updated = 0 if is_new else 1
        notes.append(f"{normalized_symbol} options snapshot stored for {snapshot_date.isoformat()} using source {source_label}.")
    except Exception as exc:  # noqa: BLE001
        status = "failed"
        notes.append(f"Options ingestion failed for {symbol}: {exc}")

    return finish_ingestion_run(
        db,
        run=run,
        started_at=started_at,
        source="nse",
        dataset="options_snapshots",
        status=status,
        processed=processed,
        inserted=inserted,
        updated=updated,
        notes=notes,
        dry_run=dry_run,
    )


def _load_options_payload_from_file(source_file: str) -> dict[str, Any]:
    path = Path(source_file)
    if not path.is_absolute():
        path = resolve_raw_data_path("options", source_file)
    payload = load_structured_payload(path)
    if isinstance(payload, list):
        return {"records": {"data": payload}}
    return payload


def _option_rows(options_data: dict[str, Any]) -> list[dict[str, Any]]:
    records = options_data.get("records", {})
    data_rows = records.get("data") if isinstance(records, dict) else None
    if isinstance(data_rows, list):
        return data_rows
    if isinstance(options_data, list):
        return options_data
    return []


def _aggregate_options(options_data: dict[str, Any]) -> dict[str, float | None]:
    call_oi = put_oi = call_change = put_change = 0.0
    iv_values: list[float] = []
    for row in _option_rows(options_data):
        call_leg = row.get("CE") or {}
        put_leg = row.get("PE") or {}
        call_oi += parse_float(call_leg.get("openInterest")) or 0.0
        put_oi += parse_float(put_leg.get("openInterest")) or 0.0
        call_change += parse_float(call_leg.get("changeinOpenInterest")) or 0.0
        put_change += parse_float(put_leg.get("changeinOpenInterest")) or 0.0
        call_iv = parse_float(call_leg.get("impliedVolatility"))
        put_iv = parse_float(put_leg.get("impliedVolatility"))
        if call_iv is not None:
            iv_values.append(call_iv)
        if put_iv is not None:
            iv_values.append(put_iv)

    call_change_pct = (call_change / call_oi * 100.0) if call_oi > 0 else 0.0
    put_change_pct = (put_change / put_oi * 100.0) if put_oi > 0 else 0.0
    avg_iv = mean(iv_values) if iv_values else None
    return {
        "call_oi": round(call_oi, 2),
        "put_oi": round(put_oi, 2),
        "call_oi_change": round(call_change_pct, 2),
        "put_oi_change": round(put_change_pct, 2),
        "avg_iv": round(avg_iv, 2) if avg_iv is not None else None,
    }


def _calculate_iv_percentile(current_iv: float | None, historical_values: list[float]) -> float | None:
    if current_iv is None:
        return None
    if not historical_values:
        return 50.0
    values = sorted(historical_values + [current_iv])
    rank = sum(1 for value in values if value <= current_iv)
    return round((rank / len(values)) * 100.0, 2)


def _first_expiry(options_data: dict[str, Any]) -> date | None:
    expiry_dates = options_data.get("records", {}).get("expiryDates", [])
    if isinstance(expiry_dates, list) and expiry_dates:
        try:
            return parse_date(expiry_dates[0])
        except ValueError:
            return None
    return None
