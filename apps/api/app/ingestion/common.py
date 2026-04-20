from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.ingestion_run import IngestionRun


COMMON_REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json, text/csv, text/plain, */*",
}


@dataclass
class GenericIngestionSummary:
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


def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def resolve_raw_data_path(*parts: str) -> Path:
    base = Path(settings.raw_data_dir).expanduser()
    if not base.is_absolute():
        base = (repo_root() / base).resolve()
    return base.joinpath(*parts)


def load_structured_payload(path: Path) -> list[dict[str, Any]] | dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    suffix = path.suffix.lower()
    if suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            records = payload.get("records")
            if isinstance(records, list):
                return records
            return payload
        raise ValueError(f"Unsupported JSON payload structure in {path}")

    if suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))

    raise ValueError(f"Unsupported file type for {path.name}. Expected JSON or CSV.")


def start_ingestion_run(db: Session, *, source: str, dataset: str) -> tuple[IngestionRun, datetime]:
    started_at = datetime.now(timezone.utc)
    run = IngestionRun(
        source=source,
        dataset=dataset,
        status="running",
        started_at=started_at,
        records_processed=0,
        records_inserted=0,
        records_updated=0,
        notes="",
    )
    db.add(run)
    db.flush()
    return run, started_at


def finish_ingestion_run(
    db: Session,
    *,
    run: IngestionRun,
    started_at: datetime,
    source: str,
    dataset: str,
    status: str,
    processed: int,
    inserted: int,
    updated: int,
    notes: list[str],
    dry_run: bool = False,
) -> GenericIngestionSummary:
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

    return GenericIngestionSummary(
        run_id=run.id,
        source=source,
        dataset=dataset,
        status=status,
        started_at=started_at,
        completed_at=completed_at,
        records_processed=processed,
        records_inserted=inserted,
        records_updated=updated,
        notes=notes,
    )


def normalize_symbol(value: Any) -> str:
    return str(value or "").strip().upper()


def parse_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%d-%b-%Y", "%d-%b-%y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unable to parse date value: {value}")


def parse_float(value: Any) -> float | None:
    if value in (None, "", "NA", "N/A", "-"):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace(",", "").replace("%", "").strip()
    if not text:
        return None
    return float(text)


def parse_int(value: Any) -> int | None:
    if value in (None, "", "NA", "N/A", "-"):
        return None
    if isinstance(value, int):
        return value
    text = str(value).replace(",", "").strip()
    if not text:
        return None
    return int(float(text))


def parse_bool(value: Any) -> bool | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y"}:
        return True
    if text in {"false", "0", "no", "n"}:
        return False
    return None
