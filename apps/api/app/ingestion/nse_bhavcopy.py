from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from io import StringIO
from pathlib import Path
import re
from typing import Callable, Iterable
from zipfile import ZipFile

import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.daily_bar import DailyBar
from app.models.ingestion_run import IngestionRun
from app.models.instrument import Instrument
from app.services.instrument_master import enrich_instrument_from_master


COMMON_REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/zip, application/octet-stream, text/csv, */*",
}


COLUMN_ALIASES = {
    "symbol": ["SYMBOL", "TckrSymb"],
    "series": ["SERIES", "SctySrs"],
    "name": ["NAME OF COMPANY", "FinInstrmNm"],
    "isin": ["ISIN", "ISIN_CODE"],
    "open_price": ["OPEN", "OpnPric"],
    "high_price": ["HIGH", "HghPric"],
    "low_price": ["LOW", "LwPric"],
    "close_price": ["CLOSE", "ClsPric"],
    "last_price": ["LAST", "LastPric"],
    "prev_close": ["PREVCLOSE", "PrevCls"],
    "total_traded_qty": ["TOTTRDQTY", "TtlTradgVol"],
    "total_traded_value": ["TOTTRDVAL", "TtlTrfVal"],
    "total_trades": ["TOTALTRADES", "TtlNbOfTxsExctd"],
    "face_value": ["FACEVALUE", "FinInstrmFaceVal"],
}


@dataclass
class BhavcopyIngestionSummary:
    run_id: str
    source: str
    dataset: str
    status: str
    started_at: datetime
    completed_at: datetime
    records_processed: int
    records_inserted: int
    records_updated: int
    notes: list[str]


class BhavcopyDownloadError(RuntimeError):
    pass


BHAVCOPY_ARCHIVE_RE = re.compile(r"BhavCopy_NSE_CM_0_0_0_(\d{8})_F_0000\.csv\.zip$")


def ingest_nse_bhavcopy_range(
    db: Session,
    start_date: date,
    end_date: date | None = None,
    include_series: Iterable[str] = ("EQ",),
    dry_run: bool = False,
    progress_callback: Callable[[dict[str, object]], None] | None = None,
) -> BhavcopyIngestionSummary:
    effective_end = end_date or start_date
    trading_days = get_trading_days(start_date, effective_end)
    total_days = len(trading_days)
    started_at = datetime.now(timezone.utc)
    run = IngestionRun(
        source="nse",
        dataset="cm_bhavcopy",
        status="running",
        started_at=started_at,
        records_processed=0,
        records_inserted=0,
        records_updated=0,
        notes="",
    )
    db.add(run)
    db.flush()

    notes: list[str] = []
    processed = 0
    inserted = 0
    updated = 0
    status = "completed"

    for day_index, current in enumerate(trading_days, start=1):
        try:
            raw_zip_path = fetch_bhavcopy_archive(current)
            rows = parse_bhavcopy_zip(raw_zip_path)
            with db.begin_nested():
                result = upsert_bhavcopy_rows(db, rows, current, include_series=set(include_series), dry_run=dry_run)
            processed += result["processed"]
            inserted += result["inserted"]
            updated += result["updated"]
            notes.append(f"{current.isoformat()}: processed {result['processed']} records from {raw_zip_path.name}.")
        except BhavcopyDownloadError as exc:
            status = "partial"
            notes.append(f"{current.isoformat()}: skipped, {exc}.")
        except Exception as exc:  # noqa: BLE001
            status = "partial"
            notes.append(f"{current.isoformat()}: failed, {exc}.")
        finally:
            if progress_callback is not None:
                progress_callback(
                    {
                        "current_date": current,
                        "completed_days": day_index,
                        "total_days": total_days,
                        "status": status,
                        "records_processed": processed,
                        "records_inserted": inserted,
                        "records_updated": updated,
                        "latest_note": notes[-1] if notes else "",
                    }
                )

    completed_at = datetime.now(timezone.utc)
    run.status = status
    run.completed_at = completed_at
    run.records_processed = processed
    run.records_inserted = inserted
    run.records_updated = updated
    run.notes = "\n".join(notes)

    if dry_run:
        db.rollback()
    else:
        db.commit()

    return BhavcopyIngestionSummary(
        run_id=run.id,
        source=run.source,
        dataset=run.dataset,
        status=status,
        started_at=started_at,
        completed_at=completed_at,
        records_processed=processed,
        records_inserted=inserted,
        records_updated=updated,
        notes=notes,
    )


def ingest_cached_nse_bhavcopy_archives(
    db: Session,
    include_series: Iterable[str] = ("EQ",),
    dry_run: bool = False,
    progress_callback: Callable[[dict[str, object]], None] | None = None,
) -> BhavcopyIngestionSummary:
    archive_records = discover_cached_bhavcopy_archives()
    started_at = datetime.now(timezone.utc)
    run = IngestionRun(
        source="local_cache",
        dataset="cm_bhavcopy_cache",
        status="running",
        started_at=started_at,
        records_processed=0,
        records_inserted=0,
        records_updated=0,
        notes="",
    )
    db.add(run)
    db.flush()

    if not archive_records:
        completed_at = datetime.now(timezone.utc)
        run.status = "failed"
        run.completed_at = completed_at
        run.notes = "No cached bhavcopy archives were found under the configured raw data directory."
        if dry_run:
            db.rollback()
        else:
            db.commit()
        return BhavcopyIngestionSummary(
            run_id=run.id,
            source=run.source,
            dataset=run.dataset,
            status=run.status,
            started_at=started_at,
            completed_at=completed_at,
            records_processed=0,
            records_inserted=0,
            records_updated=0,
            notes=[run.notes],
        )

    total_archives = len(archive_records)
    processed = 0
    inserted = 0
    updated = 0
    notes: list[str] = []
    status = "completed"

    for archive_index, (trade_date, archive_path) in enumerate(archive_records, start=1):
        try:
            rows = parse_bhavcopy_zip(archive_path)
            with db.begin_nested():
                result = upsert_bhavcopy_rows(db, rows, trade_date, include_series=set(include_series), dry_run=dry_run)
            processed += result["processed"]
            inserted += result["inserted"]
            updated += result["updated"]
            notes.append(f"{trade_date.isoformat()}: processed {result['processed']} cached records from {archive_path.name}.")
        except Exception as exc:  # noqa: BLE001
            status = "partial"
            notes.append(f"{trade_date.isoformat()}: failed to ingest cached archive {archive_path.name}, {exc}.")
        finally:
            if progress_callback is not None:
                progress_callback(
                    {
                        "current_date": trade_date,
                        "completed_days": archive_index,
                        "total_days": total_archives,
                        "status": status,
                        "records_processed": processed,
                        "records_inserted": inserted,
                        "records_updated": updated,
                        "latest_note": notes[-1] if notes else "",
                    }
                )

    completed_at = datetime.now(timezone.utc)
    run.status = status
    run.completed_at = completed_at
    run.records_processed = processed
    run.records_inserted = inserted
    run.records_updated = updated
    run.notes = "\n".join(notes)

    if dry_run:
        db.rollback()
    else:
        db.commit()

    return BhavcopyIngestionSummary(
        run_id=run.id,
        source=run.source,
        dataset=run.dataset,
        status=status,
        started_at=started_at,
        completed_at=completed_at,
        records_processed=processed,
        records_inserted=inserted,
        records_updated=updated,
        notes=notes,
    )


def fetch_bhavcopy_archive(trade_date: date) -> Path:
    filename = f"BhavCopy_NSE_CM_0_0_0_{trade_date.strftime('%Y%m%d')}_F_0000.csv.zip"
    url = f"{settings.nse_archive_base_url.rstrip('/')}/{filename}"

    raw_dir = get_raw_storage_dir(trade_date)
    raw_dir.mkdir(parents=True, exist_ok=True)
    archive_path = raw_dir / filename

    if archive_path.exists():
        return archive_path

    response = requests.get(url, headers=COMMON_REQUEST_HEADERS, timeout=30)
    if response.status_code != 200:
        raise BhavcopyDownloadError(f"download returned status {response.status_code} for inferred archive URL {url}")

    archive_path.write_bytes(response.content)
    return archive_path


def parse_bhavcopy_zip(archive_path: Path) -> list[dict[str, str]]:
    with ZipFile(archive_path) as archive:
        csv_members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if not csv_members:
            raise ValueError(f"No CSV file found in {archive_path.name}")

        with archive.open(csv_members[0], "r") as csv_file:
            text = csv_file.read().decode("utf-8-sig", errors="ignore")
            reader = csv.DictReader(StringIO(text))
            return list(reader)


def upsert_bhavcopy_rows(
    db: Session,
    rows: list[dict[str, str]],
    trade_date: date,
    include_series: set[str],
    dry_run: bool = False,
) -> dict[str, int]:
    inserted = 0
    updated = 0
    processed = 0

    for row in rows:
        normalized = normalize_bhavcopy_row(row)
        if not normalized:
            continue
        if include_series and normalized["series"] not in include_series:
            continue

        processed += 1

        instrument = resolve_instrument(
            db=db,
            symbol=normalized["symbol"],
            series=normalized["series"],
            isin=normalized["isin"],
        )

        if instrument is None:
            instrument = Instrument(
                symbol=normalized["symbol"],
                series=normalized["series"],
                name=normalized["name"],
                isin=normalized["isin"],
                sector=None,
                face_value=normalized["face_value"],
                is_active=True,
            )
            enrich_instrument_from_master(instrument)
            db.add(instrument)
            db.flush()
        else:
            maybe_update_instrument_identity(
                db=db,
                instrument=instrument,
                symbol=normalized["symbol"],
                series=normalized["series"],
            )
            if normalized["name"] and not instrument.name:
                instrument.name = normalized["name"]
            if normalized["isin"] and not instrument.isin:
                instrument.isin = normalized["isin"]
            if normalized["face_value"] is not None and instrument.face_value is None:
                instrument.face_value = normalized["face_value"]
            enrich_instrument_from_master(instrument)

        existing_bar = db.execute(
            select(DailyBar).where(
                DailyBar.instrument_id == instrument.id,
                DailyBar.trade_date == trade_date,
            )
        ).scalar_one_or_none()

        payload = dict(
            instrument_id=instrument.id,
            trade_date=trade_date,
            open_price=normalized["open_price"],
            high_price=normalized["high_price"],
            low_price=normalized["low_price"],
            close_price=normalized["close_price"],
            last_price=normalized["last_price"],
            prev_close=normalized["prev_close"],
            total_traded_qty=normalized["total_traded_qty"],
            total_traded_value=normalized["total_traded_value"],
            total_trades=normalized["total_trades"],
            deliverable_qty=None,
            deliverable_pct=None,
            source="nse_bhavcopy",
        )

        if existing_bar is None:
            db.add(DailyBar(**payload))
            inserted += 1
        else:
            for key, value in payload.items():
                setattr(existing_bar, key, value)
            updated += 1

    if not dry_run:
        db.flush()

    return {"processed": processed, "inserted": inserted, "updated": updated}


def normalize_bhavcopy_row(row: dict[str, str]) -> dict | None:
    symbol = get_first_value(row, "symbol")
    if not symbol:
        return None

    return {
        "symbol": symbol.strip(),
        "series": (get_first_value(row, "series") or "EQ").strip(),
        "name": clean_nullable_string(get_first_value(row, "name")),
        "isin": clean_nullable_string(get_first_value(row, "isin")),
        "open_price": to_decimal(get_first_value(row, "open_price")),
        "high_price": to_decimal(get_first_value(row, "high_price")),
        "low_price": to_decimal(get_first_value(row, "low_price")),
        "close_price": to_decimal(get_first_value(row, "close_price")),
        "last_price": to_optional_decimal(get_first_value(row, "last_price")),
        "prev_close": to_optional_decimal(get_first_value(row, "prev_close")),
        "total_traded_qty": to_optional_int(get_first_value(row, "total_traded_qty")),
        "total_traded_value": to_optional_decimal(get_first_value(row, "total_traded_value")),
        "total_trades": to_optional_int(get_first_value(row, "total_trades")),
        "face_value": to_optional_decimal(get_first_value(row, "face_value")),
    }


def resolve_instrument(
    db: Session,
    *,
    symbol: str,
    series: str,
    isin: str | None,
) -> Instrument | None:
    instrument = db.execute(
        select(Instrument).where(
            Instrument.symbol == symbol,
            Instrument.series == series,
        )
    ).scalar_one_or_none()
    if instrument is not None:
        return instrument

    if isin:
        instrument = db.execute(select(Instrument).where(Instrument.isin == isin)).scalar_one_or_none()
        if instrument is not None:
            return instrument

    return None


def maybe_update_instrument_identity(
    db: Session,
    *,
    instrument: Instrument,
    symbol: str,
    series: str,
) -> None:
    if instrument.symbol == symbol and instrument.series == series:
        return

    conflicting = db.execute(
        select(Instrument).where(
            Instrument.symbol == symbol,
            Instrument.series == series,
            Instrument.id != instrument.id,
        )
    ).scalar_one_or_none()
    if conflicting is not None:
        return

    instrument.symbol = symbol
    instrument.series = series


def get_first_value(row: dict[str, str], logical_name: str) -> str | None:
    for alias in COLUMN_ALIASES[logical_name]:
        if alias in row and row[alias] not in (None, "", "-"):
            return row[alias]
    return None


def to_decimal(value: str | None) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value).replace(",", "").strip())


def to_optional_decimal(value: str | None) -> Decimal | None:
    if value in (None, "", "-"):
        return None
    return Decimal(str(value).replace(",", "").strip())


def to_optional_int(value: str | None) -> int | None:
    if value in (None, "", "-"):
        return None
    return int(str(value).replace(",", "").strip())


def clean_nullable_string(value: str | None) -> str | None:
    if value in (None, "", "-"):
        return None
    return value.strip()


def get_raw_storage_dir(trade_date: date) -> Path:
    configured = Path(settings.raw_data_dir)
    if not configured.is_absolute():
        configured = (Path(__file__).resolve().parents[4] / configured).resolve()
    return configured / "nse" / "cm" / trade_date.strftime("%Y") / trade_date.strftime("%m") / trade_date.strftime("%d")


def discover_cached_bhavcopy_archives() -> list[tuple[date, Path]]:
    configured = Path(settings.raw_data_dir)
    if not configured.is_absolute():
        configured = (Path(__file__).resolve().parents[4] / configured).resolve()
    archive_root = configured / "nse" / "cm"
    if not archive_root.exists():
        return []

    by_trade_date: dict[date, Path] = {}
    for archive_path in sorted(archive_root.rglob("BhavCopy_NSE_CM_0_0_0_*_F_0000.csv.zip")):
        match = BHAVCOPY_ARCHIVE_RE.match(archive_path.name)
        if match is None:
            continue
        trade_date = datetime.strptime(match.group(1), "%Y%m%d").date()
        by_trade_date.setdefault(trade_date, archive_path)

    return sorted(by_trade_date.items(), key=lambda item: item[0])


def get_trading_days(start_date: date, end_date: date) -> list[date]:
    current = start_date
    trading_days: list[date] = []
    while current <= end_date:
        if current.weekday() < 5:
            trading_days.append(current)
        current += timedelta(days=1)
    return trading_days
