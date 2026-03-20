from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.portfolio import AnalyzePortfolioRequest, AnalyzePortfolioResponse
from app.services.db_quant_engine import analyze_portfolio


router = APIRouter()


@router.post("/portfolio", response_model=AnalyzePortfolioResponse)
def analyze_portfolio_endpoint(
    payload: AnalyzePortfolioRequest,
    db: Session = Depends(get_db),
) -> AnalyzePortfolioResponse:
    try:
        return analyze_portfolio(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
