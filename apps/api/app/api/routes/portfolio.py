from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.portfolio import GeneratePortfolioRequest, GeneratePortfolioResponse, MandateQuestionnaireResponse
from app.services.mandate import NSE_SECTOR_CODES, build_default_mandate
from app.services.db_quant_engine import generate_portfolio


router = APIRouter()


@router.get("/mandate/questionnaire", response_model=MandateQuestionnaireResponse)
def get_mandate_questionnaire() -> MandateQuestionnaireResponse:
    return MandateQuestionnaireResponse(
        investment_horizon_weeks_options=["2-4", "4-8", "8-24"],
        risk_attitude_options=["capital_preservation", "balanced", "growth"],
        sector_codes=NSE_SECTOR_CODES,
        defaults=build_default_mandate(),
    )


@router.post("/generate", response_model=GeneratePortfolioResponse)
def generate_portfolio_endpoint(
    payload: GeneratePortfolioRequest,
    db: Session = Depends(get_db),
) -> GeneratePortfolioResponse:
    try:
        return generate_portfolio(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
