from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.portfolio import BenchmarkCompareRequest, BenchmarkCompareResponse, BenchmarkSummaryResponse
from app.services.db_quant_engine import build_benchmark_compare, get_benchmark_summary


router = APIRouter()


@router.get("/summary", response_model=BenchmarkSummaryResponse)
def benchmark_summary_endpoint(
    db: Session = Depends(get_db),
) -> BenchmarkSummaryResponse:
    try:
        return get_benchmark_summary(db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/compare", response_model=BenchmarkCompareResponse)
def benchmark_compare_endpoint(
    payload: BenchmarkCompareRequest,
    db: Session = Depends(get_db),
) -> BenchmarkCompareResponse:
    try:
        return build_benchmark_compare(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
