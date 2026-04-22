from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.trade_idea import TradeIdeaListResponse, TradeIdeaModel, TradeIdeasRequest
from app.services.decision_engine import DecisionEngine


router = APIRouter()


@router.get("", response_model=TradeIdeaListResponse)
def get_trade_ideas(
    regime_aware: bool = Query(default=True),
    min_checklist_score: int = Query(default=7, ge=0, le=10),
    max_ideas: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
) -> TradeIdeaListResponse:
    engine = DecisionEngine(db)
    return engine.generate_trade_ideas(
        regime_filter=regime_aware,
        min_checklist_score=min_checklist_score,
        max_ideas=max_ideas,
    )


@router.post("/screen", response_model=TradeIdeaListResponse)
def screen_trade_ideas(
    payload: TradeIdeasRequest,
    db: Session = Depends(get_db),
) -> TradeIdeaListResponse:
    engine = DecisionEngine(db)
    return engine.generate_trade_ideas(
        regime_filter=payload.regime_aware,
        min_checklist_score=payload.min_checklist_score,
        max_ideas=payload.max_ideas,
        portfolio_value=payload.portfolio_value or 1_000_000.0,
        cash_available=payload.cash_available,
        sector_exposures=payload.sector_exposures,
        current_holdings=payload.holdings,
    )


@router.get("/{symbol}", response_model=TradeIdeaModel)
def get_trade_idea_detail(
    symbol: str,
    db: Session = Depends(get_db),
) -> TradeIdeaModel:
    engine = DecisionEngine(db)
    idea = engine.build_trade_idea(symbol.upper())
    if idea is None:
        raise HTTPException(status_code=404, detail=f"No trade idea available for {symbol.upper()}.")
    return idea
