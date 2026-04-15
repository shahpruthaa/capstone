from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


RiskMode = Literal["ULTRA_LOW", "MODERATE", "HIGH"]
RebalanceFrequency = Literal["MONTHLY", "QUARTERLY", "ANNUALLY", "NONE"]
ModelVariant = Literal["RULES", "LIGHTGBM_HYBRID"]
ModelSource = Literal["RULES", "LIGHTGBM", "ENSEMBLE"]


class AllocationModel(BaseModel):
    symbol: str
    sector: str
    weight: float = Field(..., ge=0, le=100)
    rationale: str
    top_model_drivers: list[str] = Field(default_factory=list)


class PortfolioMetricsModel(BaseModel):
    estimated_return_pct: float
    estimated_volatility_pct: float
    beta: float
    diversification_score: float


class GeneratePortfolioRequest(BaseModel):
    investment_amount: float = Field(..., gt=0)
    risk_mode: RiskMode
    as_of_date: date | None = None
    model_variant: ModelVariant = "LIGHTGBM_HYBRID"


class GeneratePortfolioResponse(BaseModel):
    model_variant: ModelVariant
    model_source: ModelSource
    model_version: str
    prediction_horizon_days: int
    active_mode: str = "rules_only"
    artifact_classification: str = "missing"
    risk_mode: RiskMode
    investment_amount: float
    allocations: list[AllocationModel]
    metrics: PortfolioMetricsModel
    holding_period_days_recommended: int = 21
    holding_period_reason: str = "Review the portfolio on the configured prediction horizon."
    notes: list[str]


class HoldingModel(BaseModel):
    symbol: str
    quantity: int = Field(..., gt=0)
    average_price: float | None = Field(default=None, gt=0)


class RebalanceActionModel(BaseModel):
    symbol: str
    action: Literal["BUY", "SELL", "HOLD"]
    target_weight: float = Field(..., ge=0, le=100)
    current_weight: float = Field(..., ge=0, le=100)
    reason: str


class AnalyzePortfolioRequest(BaseModel):
    holdings: list[HoldingModel]
    target_risk_mode: RiskMode
    model_variant: ModelVariant | None = None


class AnalyzePortfolioResponse(BaseModel):
    total_holdings: int
    portfolio_value: float
    current_beta: float
    diversification_score: float
    sector_weights: dict[str, float]
    factor_exposures: dict[str, float] = Field(default_factory=dict)
    correlation_risk: Literal["LOW", "MODERATE", "HIGH"]
    actions: list[RebalanceActionModel]
    model_variant_applied: ModelVariant
    model_source: ModelSource = "RULES"
    model_version: str = "rules"
    prediction_horizon_days: int = 21
    active_mode: str = "rules_only"
    artifact_classification: str = "missing"
    ml_predictions: dict[str, float] = Field(default_factory=dict)
    top_model_drivers_by_symbol: dict[str, list[str]] = Field(default_factory=dict)
    holding_period_days_recommended: int = 21
    holding_period_reason: str = "Review the portfolio on the configured prediction horizon."
    notes: list[str]


class PredictionValidationRow(BaseModel):
    symbol: str
    predicted_return_pct: float
    actual_return_pct: float
    absolute_error_pct: float
    direction_match: bool


class BacktestRequest(BaseModel):
    strategy_name: str = "nse-ai-portfolio"
    start_date: date
    end_date: date
    risk_mode: RiskMode
    rebalance_frequency: RebalanceFrequency = "QUARTERLY"
    stop_loss_pct: float = Field(default=0.15, ge=0, le=1)
    take_profit_pct: float = Field(default=0.3, ge=0, le=3)
    model_variant: ModelVariant = "LIGHTGBM_HYBRID"


class BacktestMetricModel(BaseModel):
    cagr_pct: float
    total_return_pct: float
    max_drawdown_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    turnover_pct: float
    win_rate_pct: float
    total_trades: int
    tax_drag_pct: float
    cost_drag_pct: float
    final_value: float
    initial_investment: float


class TaxBreakdownModel(BaseModel):
    stcg_gain: float
    ltcg_gain: float
    stcg_tax: float
    ltcg_tax: float
    cess_tax: float
    total_tax: float


class CostBreakdownModel(BaseModel):
    total_brokerage: float
    total_stt: float
    total_stamp_duty: float
    total_exchange_txn: float
    total_sebi_fees: float
    total_gst: float
    total_slippage: float
    total_costs: float


class CurvePointModel(BaseModel):
    date: date
    portfolio_value: float
    benchmark_value: float


class BacktestResultResponse(BaseModel):
    model_variant: ModelVariant
    model_source: ModelSource
    model_version: str
    prediction_horizon_days: int
    active_mode: str = "rules_only"
    artifact_classification: str = "missing"
    top_model_drivers_by_symbol: dict[str, list[str]] = Field(default_factory=dict)
    validation_as_of_date: date | None = None
    validation_horizon_days: int = 21
    validation_samples: int = 0
    validation_hit_rate_pct: float = 0.0
    validation_mae_pct: float = 0.0
    prediction_validation: list[PredictionValidationRow] = Field(default_factory=list)
    run_id: str
    status: Literal["completed"]
    metrics: BacktestMetricModel
    tax_liability: TaxBreakdownModel
    cost_breakdown: CostBreakdownModel
    equity_curve: list[CurvePointModel]
    notes: list[str]


class BenchmarkMetricModel(BaseModel):
    name: str
    description: str
    category: Literal["AI", "INDEX", "FACTOR", "AMC_STYLE"]
    construction_method: str
    is_proxy: bool
    source_window: str
    constituent_method: str
    limitations: list[str] = Field(default_factory=list)
    annual_return_pct: float
    volatility_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown_pct: float
    cagr_5y_pct: float
    expense_ratio_pct: float
    source_type: Literal["LOCAL_PROXY", "THIRD_PARTY"] = "LOCAL_PROXY"
    source_provider: str = "local_research"
    relative_accuracy_score_pct: float = 0.0


class BenchmarkGrowthPointModel(BaseModel):
    year: int
    values: dict[str, float]


class BenchmarkSummaryResponse(BaseModel):
    strategies: list[BenchmarkMetricModel]
    projected_growth: list[BenchmarkGrowthPointModel]
    notes: list[str]


class IngestBhavcopyRequest(BaseModel):
    start_date: date
    end_date: date | None = None
    include_series: list[str] = ["EQ"]
    dry_run: bool = False


class IngestBhavcopyResponse(BaseModel):
    run_id: str
    source: str
    dataset: str
    status: Literal["completed", "partial", "failed"]
    started_at: datetime
    completed_at: datetime
    records_processed: int
    records_inserted: int
    records_updated: int
    notes: list[str]


class MarketDataSummaryResponse(BaseModel):
    available: bool
    min_trade_date: date | None = None
    max_trade_date: date | None = None
    daily_bar_count: int = 0
    instrument_count: int = 0
    notes: list[str] = Field(default_factory=list)
