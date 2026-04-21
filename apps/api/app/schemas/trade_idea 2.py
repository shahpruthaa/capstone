from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class CheckResultModel(BaseModel):
    passed: bool
    score: float = Field(..., ge=0, le=1)
    reason: str


class TenPointChecklistModel(BaseModel):
    regime_check: CheckResultModel
    sector_strength: CheckResultModel
    relative_strength: CheckResultModel
    technical_setup: CheckResultModel
    options_positioning: CheckResultModel
    fii_dii_flow: CheckResultModel
    fundamental_health: CheckResultModel
    news_catalyst: CheckResultModel
    entry_stop_target: CheckResultModel
    position_sizing: CheckResultModel


class TradeIdeaModel(BaseModel):
    symbol: str
    sector: str
    timestamp: datetime
    as_of_date: date
    ensemble_score: float
    expected_return_annual: float
    top_drivers: list[str] = Field(default_factory=list)
    checklist: TenPointChecklistModel
    checklist_score: int
    entry_price: float
    stop_loss: float
    target_price: float
    risk_reward_ratio: float
    suggested_allocation_pct: float
    max_loss_per_unit: float
    regime_alignment: str
    sector_rank: int
    catalyst: str | None = None
