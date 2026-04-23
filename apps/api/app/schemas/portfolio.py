from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


RiskMode = Literal["ULTRA_LOW", "MODERATE", "HIGH"]
RebalanceFrequency = Literal["MONTHLY", "QUARTERLY", "ANNUALLY", "NONE"]
ModelVariant = Literal["RULES", "LIGHTGBM_HYBRID"]
RiskAttitude = Literal["capital_preservation", "balanced", "growth"]
InvestmentHorizon = Literal["2-4", "4-8", "8-24"]


class UserMandate(BaseModel):
    investment_horizon_weeks: InvestmentHorizon
    preferred_num_positions: int = Field(..., gt=0, le=50)
    allow_small_caps: bool = False
    risk_attitude: RiskAttitude

    @field_validator("investment_horizon_weeks", mode="before")
    @classmethod
    def normalize_horizon(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = (
            value.strip()
            .lower()
            .replace("weeks", "")
            .replace("week", "")
            .replace(" ", "")
            .replace("to", "-")
            .replace("–", "-")
        )
        return normalized


class AllocationModel(BaseModel):
    symbol: str
    name: str
    sector: str
    latest_price: float = Field(..., gt=0)
    weight: float = Field(..., ge=0, le=100)
    recommended_shares: int = Field(default=0, ge=0)
    recommended_amount: float = Field(default=0.0, ge=0)
    shares: int = Field(default=0, ge=0)
    amount: float = Field(default=0.0, ge=0)
    rationale: str
    top_model_drivers: list[str] = Field(default_factory=list)
    ml_pred_21d_return: float | None = None
    ml_pred_annual_return: float | None = None
    death_risk: float | None = None
    lstm_signal: float | None = None
    news_risk_score: float = 0.0
    news_opportunity_score: float = 0.0
    news_sentiment: float = 0.0
    news_impact: float = 0.0
    news_explanation: str = ""


class PortfolioMetricsModel(BaseModel):
    estimated_return_pct: float
    estimated_volatility_pct: float
    beta: float
    diversification_score: float


class StandardMetricDefinitionModel(BaseModel):
    return_pct: float = 0.0
    volatility_pct: float = 0.0
    sharpe_ratio: float = 0.0
    diversification_score: float | None = None
    correlation: float | None = None
    beta: float | None = None


class RuntimeDescriptorModel(BaseModel):
    variant: ModelVariant
    model_source: Literal["RULES", "ENSEMBLE"]
    active_mode: str = "rules_only"
    model_version: str = "rules"
    artifact_classification: str = "missing"
    prediction_horizon_days: int = 21


class RiskContributionModel(BaseModel):
    name: str
    weight_pct: float
    contribution_pct: float
    detail: str = ""


class PortfolioConstraintStatusModel(BaseModel):
    max_position_cap_pct: float
    max_sector_cap_pct: float
    largest_position_pct: float
    largest_position_name: str = ""
    largest_sector_weight_pct: float
    largest_sector_name: str = ""
    near_position_cap: bool = False
    near_sector_cap: bool = False


class ScenarioShockModel(BaseModel):
    name: str
    pnl_pct: float
    commentary: str


class BenchmarkRelativeStatsModel(BaseModel):
    benchmark_name: str
    active_share_pct: float = 0.0
    tracking_error_pct: float = 0.0
    ex_ante_alpha_pct: float = 0.0
    information_ratio: float = 0.0


class PortfolioFitSummaryModel(BaseModel):
    summary: str
    risk_level: str
    diversification: str
    concentration: str
    next_action: str


class GeneratePortfolioRequest(BaseModel):
    capital_amount: float = Field(..., gt=0)
    mandate: UserMandate
    as_of_date: date | None = None
    model_variant: ModelVariant = "LIGHTGBM_HYBRID"


class GeneratePortfolioResponse(BaseModel):
    model_variant: ModelVariant
    model_source: Literal["RULES", "ENSEMBLE"]
    model_version: str
    prediction_horizon_days: int
    capital_amount: float
    mandate: UserMandate
    lookback_window_days: int
    expected_holding_period_days: int
    allocations: list[AllocationModel]
    metrics: PortfolioMetricsModel
    standard_metrics: StandardMetricDefinitionModel = Field(default_factory=StandardMetricDefinitionModel)
    factor_exposures: dict[str, float] = Field(default_factory=dict)
    position_risk_contributions: list[RiskContributionModel] = Field(default_factory=list)
    sector_risk_contributions: list[RiskContributionModel] = Field(default_factory=list)
    constraints: PortfolioConstraintStatusModel | None = None
    turnover_estimate_pct: float = 0.0
    deployment_efficiency_pct: float = 0.0
    residual_cash: float = 0.0
    scenario_tests: list[ScenarioShockModel] = Field(default_factory=list)
    benchmark_relative: BenchmarkRelativeStatsModel | None = None
    portfolio_fit_summary: PortfolioFitSummaryModel | None = None
    runtime: RuntimeDescriptorModel | None = None
    holding_period_days_recommended: int = 21
    holding_period_reason: str = "Review the portfolio on the configured prediction horizon."
    regime_warning: str | None = None
    notes: list[str]


class MandateQuestionnaireResponse(BaseModel):
    investment_horizon_weeks_options: list[InvestmentHorizon]
    risk_attitude_options: list[RiskAttitude]
    sector_codes: list[str]
    defaults: UserMandate


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
    avg_pairwise_correlation: float
    sector_weights: dict[str, float]
    largest_sector: str = ""
    largest_sector_weight: float = 0.0
    factor_exposures: dict[str, float] = Field(default_factory=dict)
    correlation_risk: Literal["LOW", "MODERATE", "HIGH"]
    actions: list[RebalanceActionModel]
    health_label: Literal["GOOD", "OKAY", "CAUTION"] = "OKAY"
    health_summary: str = ""
    risk_assessment: str = ""
    diversification_assessment: str = ""
    concentration_assessment: str = ""
    factor_assessment: str = ""
    correlation_assessment: str = ""
    benchmark_assessment: str = ""
    idiosyncratic_risk_assessment: str = ""
    rebalance_summary: str = ""
    portfolio_fit_summary: PortfolioFitSummaryModel | None = None
    standard_metrics: StandardMetricDefinitionModel = Field(default_factory=StandardMetricDefinitionModel)
    recommended_actions: list[str] = Field(default_factory=list)
    model_variant_applied: ModelVariant
    model_source: Literal["RULES", "ENSEMBLE"] = "RULES"
    active_mode: str = "rules_only"
    model_version: str = "rules"
    artifact_classification: str = "missing"
    prediction_horizon_days: int = 21
    runtime: RuntimeDescriptorModel | None = None
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
    risk_mode: RiskMode | None = None
    mandate: UserMandate | None = None
    capital_amount: float | None = Field(default=None, gt=0)
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
    total_frictional_drag_pct: float = 0.0


class CurvePointModel(BaseModel):
    date: date
    portfolio_value: float
    benchmark_value: float


class BacktestResultResponse(BaseModel):
    model_variant: ModelVariant
    model_source: Literal["RULES", "ENSEMBLE"]
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
    runtime: RuntimeDescriptorModel | None = None
    notes: list[str]


class CompareAllocationInputModel(BaseModel):
    symbol: str
    weight_pct: float = Field(..., ge=0, le=100)


class BenchmarkCompareRequest(BaseModel):
    capital_amount: float | None = Field(default=None, gt=0)
    mandate: UserMandate | None = None
    allocations: list[CompareAllocationInputModel] = Field(default_factory=list)
    benchmark_name: str | None = None
    model_variant: ModelVariant | None = None


class BenchmarkSeriesPointModel(BaseModel):
    date: date
    strategy_returns: dict[str, float]
    rolling_excess_return: dict[str, float] = Field(default_factory=dict)
    rolling_sharpe: dict[str, float] = Field(default_factory=dict)


class BenchmarkCompareStatsModel(BaseModel):
    strategy_name: str
    annual_return_pct: float
    volatility_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    tracking_error_pct: float = 0.0
    information_ratio: float = 0.0
    downside_capture_pct: float = 0.0
    upside_capture_pct: float = 0.0
    drawdown_duration_days: int = 0
    recovery_days: int = 0
    active_share_pct: float = 0.0
    net_of_cost_return_pct: float = 0.0
    net_of_tax_return_pct: float = 0.0
    ex_ante_alpha_pct: float = 0.0
    benchmark_name: str = ""
    matched_on: str = ""


class BenchmarkCompareResponse(BaseModel):
    runtime: RuntimeDescriptorModel | None = None
    portfolio_fit_summary: PortfolioFitSummaryModel | None = None
    benchmark_match_summary: str = ""
    strategies: list[BenchmarkCompareStatsModel]
    series: list[BenchmarkSeriesPointModel] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


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
    session_status: dict[str, object] | None = None
    notes: list[str] = Field(default_factory=list)


class MarketTrendBlockModel(BaseModel):
    index_symbol: str
    spot: float
    dma50: float
    dma200: float
    above_50_dma: bool
    above_200_dma: bool
    breadth_above_50_pct: float
    breadth_above_200_pct: float
    realized_volatility_pct: float
    drawdown_pct: float
    drawdown_state: str


class MarketFactorWeatherItemModel(BaseModel):
    factor: str
    leadership_score: float
    leader: str
    note: str
    data_quality: Literal["live", "proxy", "placeholder"] = "live"


class CrossAssetToneItemModel(BaseModel):
    asset: str
    tone: str
    move_pct: float
    note: str
    data_quality: Literal["live", "proxy", "placeholder"] = "proxy"


class SectorRelativeStrengthModel(BaseModel):
    sector: str
    return_1m_pct: float
    return_3m_pct: float
    return_6m_pct: float
    earnings_revision_trend: str
    note: str = ""


class MarketDashboardResponse(BaseModel):
    runtime: RuntimeDescriptorModel | None = None
    trend: MarketTrendBlockModel
    factor_weather: list[MarketFactorWeatherItemModel]
    cross_asset_tone: list[CrossAssetToneItemModel]
    sector_relative_strength: list[SectorRelativeStrengthModel]
    what_this_means_now: PortfolioFitSummaryModel | None = None
    notes: list[str] = Field(default_factory=list)
