from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.trade_idea import TradeIdeaModel
from app.services.decision_engine import DecisionEngine


router = APIRouter()


@router.get("", response_model=list[TradeIdeaModel])
def get_trade_ideas(
    regime_aware: bool = Query(default=True),
    min_checklist_score: int = Query(default=7, ge=0, le=10),
    max_ideas: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
) -> list[TradeIdeaModel]:
    engine = DecisionEngine(db)
    return engine.generate_trade_ideas(
        regime_filter=regime_aware,
        min_checklist_score=min_checklist_score,
        max_ideas=max_ideas,
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
