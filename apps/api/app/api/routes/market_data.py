from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.ingestion.nse_bhavcopy import ingest_nse_bhavcopy_range
from app.schemas.portfolio import IngestBhavcopyRequest, IngestBhavcopyResponse


router = APIRouter()


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
