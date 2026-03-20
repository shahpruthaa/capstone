from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.portfolio import GeneratePortfolioRequest, GeneratePortfolioResponse
from app.services.db_quant_engine import generate_portfolio


router = APIRouter()


@router.post("/generate", response_model=GeneratePortfolioResponse)
def generate_portfolio_endpoint(
    payload: GeneratePortfolioRequest,
    db: Session = Depends(get_db),
) -> GeneratePortfolioResponse:
    try:
        return generate_portfolio(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
