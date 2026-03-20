from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.portfolio import (
    BacktestRequest,
    BacktestResultResponse,
)
from app.services.db_quant_engine import get_backtest_result, run_backtest


router = APIRouter()


@router.post("/run", response_model=BacktestResultResponse)
def run_backtest_endpoint(
    payload: BacktestRequest,
    db: Session = Depends(get_db),
) -> BacktestResultResponse:
    try:
        return run_backtest(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{run_id}", response_model=BacktestResultResponse)
def get_backtest_endpoint(
    run_id: str,
    db: Session = Depends(get_db),
) -> BacktestResultResponse:
    try:
        return get_backtest_result(db, run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
