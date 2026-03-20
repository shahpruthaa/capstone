from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.portfolio import BenchmarkSummaryResponse
from app.services.db_quant_engine import get_benchmark_summary


router = APIRouter()


@router.get("/summary", response_model=BenchmarkSummaryResponse)
def benchmark_summary_endpoint(
    db: Session = Depends(get_db),
) -> BenchmarkSummaryResponse:
    try:
        return get_benchmark_summary(db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
