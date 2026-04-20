from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class IngestionJobResponse(BaseModel):
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


class IngestOptionsRequest(BaseModel):
    symbol: str
    snapshot_date: date
    expiry_date: date | None = None
    source_file: str | None = None
    dry_run: bool = False


class IngestInstitutionalFlowsRequest(BaseModel):
    flow_date: date | None = None
    source_file: str
    dry_run: bool = False


class IngestFundamentalsRequest(BaseModel):
    quarter_end: date | None = None
    source_file: str
    dry_run: bool = False


class IngestMarketRegimeRequest(BaseModel):
    start_date: date
    end_date: date | None = None
    dry_run: bool = False
