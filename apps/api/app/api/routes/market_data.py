from sqlalchemy import func, select
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.ingestion.fundamentals import ingest_fundamental_snapshots
from app.ingestion.institutional_flows import ingest_institutional_flows
from app.ingestion.market_regime import ingest_market_regime_range
from app.ingestion.nse_bhavcopy import ingest_nse_bhavcopy_range
from app.ingestion.nse_options import ingest_options_snapshot
from app.models.daily_bar import DailyBar
from app.models.instrument import Instrument
from app.schemas.ingestion import (
    IngestionJobResponse,
    IngestFundamentalsRequest,
    IngestInstitutionalFlowsRequest,
    IngestMarketRegimeRequest,
    IngestOptionsRequest,
)
from app.schemas.portfolio import IngestBhavcopyRequest, IngestBhavcopyResponse, MarketDashboardResponse, MarketDataSummaryResponse
from app.services.db_quant_engine import build_market_dashboard


router = APIRouter()


@router.get("/summary", response_model=MarketDataSummaryResponse)
def market_data_summary_endpoint(
    db: Session = Depends(get_db),
) -> MarketDataSummaryResponse:
    min_trade_date, max_trade_date = db.execute(select(func.min(DailyBar.trade_date), func.max(DailyBar.trade_date))).one()
    daily_bar_count = int(db.execute(select(func.count(DailyBar.id))).scalar_one() or 0)
    instrument_count = int(db.execute(select(func.count(Instrument.id))).scalar_one() or 0)

    notes: list[str] = []
    if max_trade_date is None:
        notes.append("No daily bars are loaded in PostgreSQL yet.")
    else:
        notes.append(f"Local market data is available from {min_trade_date.isoformat()} to {max_trade_date.isoformat()}.")

    return MarketDataSummaryResponse(
        available=max_trade_date is not None,
        min_trade_date=min_trade_date,
        max_trade_date=max_trade_date,
        daily_bar_count=daily_bar_count,
        instrument_count=instrument_count,
        notes=notes,
    )


@router.get("/regime", response_model=MarketDashboardResponse)
def market_regime_endpoint(
    db: Session = Depends(get_db),
) -> MarketDashboardResponse:
    return build_market_dashboard(db)


@router.post("/ingestions/nse-bhavcopy", response_model=IngestBhavcopyResponse)
def ingest_nse_bhavcopy_endpoint(
    payload: IngestBhavcopyRequest,
    db: Session = Depends(get_db),
) -> IngestBhavcopyResponse:
    summary = ingest_nse_bhavcopy_range(
        db=db,
        start_date=payload.start_date,
        end_date=payload.end_date,
        include_series=payload.include_series,
        dry_run=payload.dry_run,
    )
    return IngestBhavcopyResponse(
        run_id=summary.run_id,
        source=summary.source,
        dataset=summary.dataset,
        status=summary.status,
        started_at=summary.started_at,
        completed_at=summary.completed_at,
        records_processed=summary.records_processed,
        records_inserted=summary.records_inserted,
        records_updated=summary.records_updated,
        notes=summary.notes,
    )


@router.post("/ingestions/options", response_model=IngestionJobResponse)
def ingest_options_endpoint(
    payload: IngestOptionsRequest,
    db: Session = Depends(get_db),
) -> IngestionJobResponse:
    summary = ingest_options_snapshot(
        db=db,
        symbol=payload.symbol,
        snapshot_date=payload.snapshot_date,
        expiry_date=payload.expiry_date,
        source_file=payload.source_file,
        dry_run=payload.dry_run,
    )
    return IngestionJobResponse(**summary.__dict__)


@router.post("/ingestions/institutional-flows", response_model=IngestionJobResponse)
def ingest_institutional_flows_endpoint(
    payload: IngestInstitutionalFlowsRequest,
    db: Session = Depends(get_db),
) -> IngestionJobResponse:
    summary = ingest_institutional_flows(
        db=db,
        flow_date=payload.flow_date,
        source_file=payload.source_file,
        dry_run=payload.dry_run,
    )
    return IngestionJobResponse(**summary.__dict__)


@router.post("/ingestions/fundamentals", response_model=IngestionJobResponse)
def ingest_fundamentals_endpoint(
    payload: IngestFundamentalsRequest,
    db: Session = Depends(get_db),
) -> IngestionJobResponse:
    summary = ingest_fundamental_snapshots(
        db=db,
        quarter_end=payload.quarter_end,
        source_file=payload.source_file,
        dry_run=payload.dry_run,
    )
    return IngestionJobResponse(**summary.__dict__)


@router.post("/ingestions/market-regime", response_model=IngestionJobResponse)
def ingest_market_regime_endpoint(
    payload: IngestMarketRegimeRequest,
    db: Session = Depends(get_db),
) -> IngestionJobResponse:
    summary = ingest_market_regime_range(
        db=db,
        start_date=payload.start_date,
        end_date=payload.end_date,
        dry_run=payload.dry_run,
    )
    return IngestionJobResponse(**summary.__dict__)
