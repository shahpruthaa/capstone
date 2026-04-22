from __future__ import annotations

from datetime import date, datetime

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.portfolio import PortfolioFitSummaryModel, RuntimeDescriptorModel


class CheckResultModel(BaseModel):
    passed: bool
    score: float = Field(..., ge=0, le=1)
    reason: str
    data_quality: Literal["live", "proxy", "placeholder"] = "live"


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
    suggested_allocation_value: float = 0.0
    suggested_units: int = 0
    max_loss_per_unit: float
    regime_alignment: str
    sector_rank: int
    catalyst: str | None = None
    expected_holding_period_days: int = 21
    liquidity_slippage_bps: float = 0.0
    liquidity_commentary: str = ""
    event_calendar: list[str] = Field(default_factory=list)
    overlap_with_holdings: list[str] = Field(default_factory=list)
    duplicate_factor_bets: list[str] = Field(default_factory=list)
    hedge_factor_bets: list[str] = Field(default_factory=list)
    marginal_risk_contribution_pct: float = 0.0
    portfolio_fit_summary: str = ""
    realized_hit_rate_by_type_pct: float | None = None


class TradeIdeaContextModel(BaseModel):
    symbol: str
    sector: str
    weight_pct: float = Field(..., ge=0, le=100)


class TradeIdeasRequest(BaseModel):
    regime_aware: bool = True
    min_checklist_score: int = Field(default=7, ge=0, le=10)
    max_ideas: int = Field(default=10, ge=1, le=50)
    portfolio_value: float | None = Field(default=None, gt=0)
    cash_available: float | None = Field(default=None, ge=0)
    sector_exposures: dict[str, float] = Field(default_factory=dict)
    holdings: list[TradeIdeaContextModel] = Field(default_factory=list)


class TradeIdeaListResponse(BaseModel):
    runtime: RuntimeDescriptorModel | None = None
    portfolio_fit_summary: PortfolioFitSummaryModel | None = None
    notes: list[str] = Field(default_factory=list)
    ideas: list[TradeIdeaModel] = Field(default_factory=list)
