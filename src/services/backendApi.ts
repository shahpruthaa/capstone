import { LIQUID_ASSETS, NSE_STOCKS, Stock } from '../data/stocks';
import { ComparisonResult, BenchmarkStrategy, getComparisonResult } from './benchmarkService';
import { BacktestConfig, BacktestResult } from './backtestEngine';
import {
  AnalysisResult,
  Portfolio,
  RiskProfile,
  analyzePortfolio,
} from './portfolioService';
import {
  BenchmarkRelativeStats,
  CrossAssetToneItem,
  defaultRuntimeDescriptor,
  MarketFactorWeatherItem,
  MarketTrendBlock,
  PortfolioConstraintStatus,
  PortfolioFitSummary,
  RiskContribution,
  RuntimeDescriptor,
  ScenarioShock,
  SectorRelativeStrength,
  StandardMetrics,
} from './analyticsSchema';

const viteEnv = (import.meta as ImportMeta & { env?: Record<string, string | undefined> }).env;
export const API_BASE_URL = viteEnv?.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
const ALL_STOCKS = [...NSE_STOCKS, ...LIQUID_ASSETS];

type ApiRiskMode = 'ULTRA_LOW' | 'MODERATE' | 'HIGH';
export type ModelVariant = 'RULES' | 'LIGHTGBM_HYBRID';
export type RiskAttitude = 'capital_preservation' | 'balanced' | 'growth';
export type InvestmentHorizon = '2-4' | '4-8' | '8-24';

export interface UserMandate {
  investment_horizon_weeks: InvestmentHorizon;
  preferred_num_positions: number;
  allow_small_caps: boolean;
  risk_attitude: RiskAttitude;
}

export interface MandateQuestionnaire {
  investment_horizon_weeks_options: InvestmentHorizon[];
  risk_attitude_options: RiskAttitude[];
  sector_codes: string[];
  defaults: UserMandate;
}

export interface MarketNewsArticle {
  headline: string;
  summary: string;
  source: string;
  published_at: string;
  involved_regions: string[];
  affected_sectors: string[];
  sentiment_score: number;
  impact_score: number;
  explanation: string;
  url?: string | null;
}

export interface MarketContext {
  generated_at: string;
  articles: MarketNewsArticle[];
  sector_sentiment: Record<string, number>;
  overall_market_sentiment: number;
  top_event_summary: string;
}

export interface CurrentModelStatus {
  available: boolean;
  variant: ModelVariant;
  modelVersion?: string;
  predictionHorizonDays?: number;
  trainingMode?: string;
  artifactClassification?: 'bootstrap' | 'standard';
  validationMetrics?: Record<string, unknown>;
  validationSummary?: Record<string, unknown>;
  trainingMetadata?: Record<string, unknown>;
  evaluationReport?: Record<string, unknown>;
  reason?: string;
  runtimeSitePackages?: string;
  notes?: string[];
  healthScorePct?: number;
  currentSignalsAsOfDate?: string;
  currentSignals?: Array<{
    symbol: string;
    sector: string;
    action: 'BUY' | 'SELL' | 'HOLD';
    confidence: number;
    predictedReturn21dPct: number;
    predictedAnnualReturnPct: number;
    topDrivers: string[];
  }>;
  validationOverview?: {
    available: boolean;
    modelVersion?: string;
    trainingMode?: string;
    predictionHorizonDays?: number;
    selectionStatus?: string;
    foldCount?: number;
    sampleCount?: number;
    oosSharpeRatio?: number;
    informationCoefficient?: number;
    hitRatePct?: number;
    avgTopBottomSpreadPct?: number;
    walkForwardEquityCurve?: Array<{
      date: string;
      equityIndex: number;
      periodReturnPct: number;
      informationCoefficient: number;
      hitRatePct: number;
      sampleCount: number;
    }>;
    notes?: string[];
  };
}

export interface MarketDataSummary {
  available: boolean;
  minTradeDate?: string;
  maxTradeDate?: string;
  dailyBarCount: number;
  instrumentCount: number;
  sessionStatus?: {
    exchange: string;
    timezone: string;
    status: string;
    label: string;
    reason: string;
    isTradingDay: boolean;
    sessionDate: string;
    currentTime: string;
    nextOpenAt?: string;
    nextCloseAt?: string;
    holidayName?: string | null;
    calendarSource?: string;
  };
  notes: string[];
}

export interface MarketDashboard {
  runtime?: RuntimeDescriptor;
  trend: MarketTrendBlock;
  factorWeather: MarketFactorWeatherItem[];
  crossAssetTone: CrossAssetToneItem[];
  sectorRelativeStrength: SectorRelativeStrength[];
  whatThisMeansNow?: PortfolioFitSummary | null;
  notes: string[];
}

export interface TradeIdeaCheck {
  passed: boolean;
  score: number;
  reason: string;
  dataQuality?: 'live' | 'proxy' | 'placeholder';
}

export interface TradeIdeaChecklist {
  regime_check: TradeIdeaCheck;
  sector_strength: TradeIdeaCheck;
  relative_strength: TradeIdeaCheck;
  technical_setup: TradeIdeaCheck;
  options_positioning: TradeIdeaCheck;
  fii_dii_flow: TradeIdeaCheck;
  fundamental_health: TradeIdeaCheck;
  news_catalyst: TradeIdeaCheck;
  entry_stop_target: TradeIdeaCheck;
  position_sizing: TradeIdeaCheck;
}

export interface TradeIdea {
  symbol: string;
  sector: string;
  timestamp: string;
  as_of_date: string;
  ensemble_score: number;
  expected_return_annual: number;
  top_drivers: string[];
  checklist: TradeIdeaChecklist;
  checklist_score: number;
  entry_price: number;
  stop_loss: number;
  target_price: number;
  risk_reward_ratio: number;
  suggested_allocation_pct: number;
  suggested_allocation_value: number;
  suggested_units: number;
  max_loss_per_unit: number;
  regime_alignment: string;
  sector_rank: number;
  catalyst?: string | null;
  expected_holding_period_days: number;
  liquidity_slippage_bps: number;
  liquidity_commentary: string;
  event_calendar: string[];
  overlap_with_holdings: string[];
  duplicate_factor_bets: string[];
  hedge_factor_bets: string[];
  marginal_risk_contribution_pct: number;
  portfolio_fit_summary: string;
  realized_hit_rate_by_type_pct?: number | null;
}

export interface TradeIdeasResponse {
  runtime?: RuntimeDescriptor;
  portfolioFitSummary?: PortfolioFitSummary | null;
  notes: string[];
  ideas: TradeIdea[];
}

export interface BenchmarkCompareStats {
  strategyName: string;
  annualReturnPct: number;
  volatilityPct: number;
  sharpeRatio: number;
  maxDrawdownPct: number;
  trackingErrorPct: number;
  informationRatio: number;
  downsideCapturePct: number;
  upsideCapturePct: number;
  drawdownDurationDays: number;
  recoveryDays: number;
  activeSharePct: number;
  netOfCostReturnPct: number;
  netOfTaxReturnPct: number;
  exAnteAlphaPct: number;
  benchmarkName: string;
  matchedOn: string;
}

export interface BenchmarkComparePoint {
  date: string;
  strategyReturns: Record<string, number>;
  rollingExcessReturn: Record<string, number>;
  rollingSharpe: Record<string, number>;
}

export interface BenchmarkCompareResponse {
  runtime?: RuntimeDescriptor;
  portfolioFitSummary?: PortfolioFitSummary | null;
  benchmarkMatchSummary: string;
  strategies: BenchmarkCompareStats[];
  series: BenchmarkComparePoint[];
  notes: string[];
}

interface ApiGeneratePortfolioResponse {
  model_variant: ModelVariant;
  model_source: 'RULES' | 'ENSEMBLE';
  model_version: string;
  prediction_horizon_days: number;
  capital_amount: number;
  mandate: UserMandate;
  lookback_window_days: number;
  expected_holding_period_days: number;
  allocations: {
    symbol: string;
    name: string;
    sector: string;
    latest_price: number;
    weight: number;
    recommended_shares: number;
    recommended_amount: number;
    shares?: number;
    amount?: number;
    rationale: string;
    top_model_drivers?: string[];
    ml_pred_21d_return?: number | null;
    ml_pred_annual_return?: number | null;
    death_risk?: number | null;
    lstm_signal?: number | null;
    news_risk_score: number;
    news_opportunity_score: number;
    news_sentiment: number;
    news_impact: number;
    news_explanation: string;
  }[];
  metrics: {
    estimated_return_pct: number;
    estimated_volatility_pct: number;
    beta: number;
    diversification_score: number;
  };
  standard_metrics?: {
    return_pct: number;
    volatility_pct: number;
    sharpe_ratio: number;
    diversification_score?: number;
    correlation?: number;
    beta?: number;
  };
  factor_exposures?: Record<string, number>;
  position_risk_contributions?: Array<{ name: string; weight_pct: number; contribution_pct: number; detail: string }>;
  sector_risk_contributions?: Array<{ name: string; weight_pct: number; contribution_pct: number; detail: string }>;
  constraints?: {
    max_position_cap_pct: number;
    max_sector_cap_pct: number;
    largest_position_pct: number;
    largest_position_name: string;
    largest_sector_weight_pct: number;
    largest_sector_name: string;
    near_position_cap: boolean;
    near_sector_cap: boolean;
  };
  turnover_estimate_pct?: number;
  deployment_efficiency_pct?: number;
  residual_cash?: number;
  scenario_tests?: Array<{ name: string; pnl_pct: number; commentary: string }>;
  benchmark_relative?: {
    benchmark_name: string;
    active_share_pct: number;
    tracking_error_pct: number;
    ex_ante_alpha_pct: number;
    information_ratio: number;
  };
  portfolio_fit_summary?: {
    summary: string;
    risk_level: string;
    diversification: string;
    concentration: string;
    next_action: string;
  };
  runtime?: {
    variant: ModelVariant;
    model_source: 'RULES' | 'ENSEMBLE';
    active_mode: string;
    model_version: string;
    artifact_classification: string;
    prediction_horizon_days: number;
  };
  regime_warning?: string | null;
  notes?: string[];
}

interface ApiAnalyzePortfolioResponse {
  total_holdings: number;
  portfolio_value: number;
  current_beta: number;
  diversification_score: number;
  avg_pairwise_correlation: number;
  sector_weights: Record<string, number>;
  largest_sector?: string;
  largest_sector_weight?: number;
  factor_exposures?: Record<string, number>;
  correlation_risk: 'LOW' | 'MODERATE' | 'HIGH';
  actions: { symbol: string; action: 'BUY' | 'SELL' | 'HOLD'; target_weight: number; current_weight: number; reason: string }[];
  health_label?: 'GOOD' | 'OKAY' | 'CAUTION';
  health_summary?: string;
  risk_assessment?: string;
  diversification_assessment?: string;
  concentration_assessment?: string;
  factor_assessment?: string;
  correlation_assessment?: string;
  benchmark_assessment?: string;
  idiosyncratic_risk_assessment?: string;
  rebalance_summary?: string;
  portfolio_fit_summary?: {
    summary: string;
    risk_level: string;
    diversification: string;
    concentration: string;
    next_action: string;
  };
  standard_metrics?: {
    return_pct: number;
    volatility_pct: number;
    sharpe_ratio: number;
    diversification_score?: number;
    correlation?: number;
    beta?: number;
  };
  recommended_actions?: string[];
  model_variant_applied: ModelVariant;
  model_source?: 'RULES' | 'ENSEMBLE';
  active_mode?: string;
  model_version?: string;
  artifact_classification?: string;
  prediction_horizon_days?: number;
  runtime?: {
    variant: ModelVariant;
    model_source: 'RULES' | 'ENSEMBLE';
    active_mode: string;
    model_version: string;
    artifact_classification: string;
    prediction_horizon_days: number;
  };
  ml_predictions?: Record<string, number>;
  top_model_drivers_by_symbol?: Record<string, string[]>;
  holding_period_days_recommended?: number;
  holding_period_reason?: string;
  notes: string[];
}

interface ApiBacktestResponse {
  model_variant: ModelVariant;
  model_source: 'RULES' | 'ENSEMBLE';
  model_version: string;
  prediction_horizon_days: number;
  top_model_drivers_by_symbol?: Record<string, string[]>;
  metrics: {
    cagr_pct: number;
    total_return_pct: number;
    max_drawdown_pct: number;
    sharpe_ratio: number;
    sortino_ratio: number;
    calmar_ratio: number;
    turnover_pct: number;
    win_rate_pct: number;
    total_trades: number;
    final_value: number;
    initial_investment: number;
  };
  tax_liability: {
    stcg_gain: number;
    ltcg_gain: number;
    stcg_tax: number;
    ltcg_tax: number;
    cess_tax: number;
    total_tax: number;
  };
  cost_breakdown: {
    total_brokerage: number;
    total_stt: number;
    total_stamp_duty: number;
    total_exchange_txn: number;
    total_sebi_fees: number;
    total_gst: number;
    total_slippage: number;
    total_costs: number;
  };
  equity_curve: { date: string; portfolio_value: number; benchmark_value: number }[];
  notes?: string[];
}

interface ApiBenchmarkResponse {
  strategies: {
    name: string;
    description: string;
    category: 'AI' | 'INDEX' | 'FACTOR' | 'AMC_STYLE';
    construction_method: string;
    is_proxy: boolean;
    source_window: string;
    constituent_method: string;
    limitations: string[];
    annual_return_pct: number;
    volatility_pct: number;
    sharpe_ratio: number;
    sortino_ratio: number;
    max_drawdown_pct: number;
    cagr_5y_pct: number;
    expense_ratio_pct: number;
    source_type?: 'LOCAL_PROXY' | 'THIRD_PARTY';
    source_provider?: string;
    relative_accuracy_score_pct?: number;
  }[];
  projected_growth: { year: number; values: Record<string, number> }[];
  runtime?: {
    variant: ModelVariant;
    model_source: 'RULES' | 'ENSEMBLE';
    active_mode: string;
    model_version: string;
    artifact_classification: string;
    prediction_horizon_days: number;
  };
  notes?: string[];
}

interface ApiBenchmarkCompareResponse {
  runtime?: {
    variant: ModelVariant;
    model_source: 'RULES' | 'ENSEMBLE';
    active_mode: string;
    model_version: string;
    artifact_classification: string;
    prediction_horizon_days: number;
  };
  portfolio_fit_summary?: {
    summary: string;
    risk_level: string;
    diversification: string;
    concentration: string;
    next_action: string;
  };
  benchmark_match_summary: string;
  strategies: Array<{
    strategy_name: string;
    annual_return_pct: number;
    volatility_pct: number;
    sharpe_ratio: number;
    max_drawdown_pct: number;
    tracking_error_pct: number;
    information_ratio: number;
    downside_capture_pct: number;
    upside_capture_pct: number;
    drawdown_duration_days: number;
    recovery_days: number;
    active_share_pct: number;
    net_of_cost_return_pct: number;
    net_of_tax_return_pct: number;
    ex_ante_alpha_pct: number;
    benchmark_name: string;
    matched_on: string;
  }>;
  series: Array<{
    date: string;
    strategy_returns: Record<string, number>;
    rolling_excess_return: Record<string, number>;
    rolling_sharpe: Record<string, number>;
  }>;
  notes?: string[];
}

interface ApiObservabilityKpiResponse {
  generated_at: string;
  phase_gates: {
    phase_0_data_contracts: boolean;
    phase_1_benchmark_fidelity: boolean;
    phase_2_test_harness: boolean;
    phase_3_engineering_health: boolean;
    phase_4_stable_baseline: boolean;
  };
  reliability: {
    generate_latency_ms_p95?: number | null;
    generate_error_rate_pct?: number | null;
    benchmark_latency_ms_p95?: number | null;
    benchmark_error_rate_pct?: number | null;
    sample_window: string;
    sample_size: number;
    measurement_method: string;
    notes?: string[];
  };
  quality: {
    news_impact_precision_proxy_pct?: number | null;
    benchmark_tracking_error_proxy_pct?: number | null;
    sample_window: string;
    measurement_method: string;
    notes?: string[];
  };
  ml_robustness: {
    out_of_sample_stability_pct?: number | null;
    fallback_rate_pct?: number | null;
    fallback_rate_by_cause: Record<string, number>;
    sample_window: string;
    measurement_method: string;
    notes?: string[];
  };
  engineering_health: {
    pr_pass_rate_pct?: number | null;
    flaky_test_rate_pct?: number | null;
    mean_time_to_detect_regressions_minutes?: number | null;
    sample_window: string;
    measurement_method: string;
    notes?: string[];
  };
  notes?: string[];
}

interface ApiCurrentModelStatusResponse {
  available: boolean;
  variant: ModelVariant;
  model_version?: string;
  prediction_horizon_days?: number;
  training_mode?: string;
  artifact_classification?: 'bootstrap' | 'standard';
  validation_metrics?: Record<string, unknown>;
  validation_summary?: Record<string, unknown>;
  training_metadata?: Record<string, unknown>;
  evaluation_report?: Record<string, unknown>;
  runtime_site_packages?: string;
  reason?: string;
  notes?: string[];
  health_score_pct?: number;
  current_signals_as_of_date?: string;
  current_signals?: Array<{
    symbol: string;
    sector: string;
    action: 'BUY' | 'SELL' | 'HOLD';
    confidence: number;
    predicted_return_21d_pct: number;
    predicted_annual_return_pct: number;
    top_drivers: string[];
  }>;
  validation_overview?: {
    available: boolean;
    model_version?: string;
    training_mode?: string;
    prediction_horizon_days?: number;
    selection_status?: string;
    fold_count?: number;
    sample_count?: number;
    oos_sharpe_ratio?: number;
    information_coefficient?: number;
    hit_rate_pct?: number;
    avg_top_bottom_spread_pct?: number;
    walk_forward_equity_curve?: Array<{
      date: string;
      equity_index: number;
      period_return_pct: number;
      information_coefficient: number;
      hit_rate_pct: number;
      sample_count: number;
    }>;
    notes?: string[];
  };
}

interface ApiMarketDataSummaryResponse {
  available: boolean;
  min_trade_date?: string;
  max_trade_date?: string;
  daily_bar_count: number;
  instrument_count: number;
  session_status?: {
    exchange: string;
    timezone: string;
    status: string;
    label: string;
    reason: string;
    is_trading_day: boolean;
    session_date: string;
    current_time: string;
    next_open_at?: string;
    next_close_at?: string;
    holiday_name?: string | null;
    calendar_source?: string;
  };
  notes?: string[];
}

interface ApiMarketDashboardResponse {
  runtime?: {
    variant: ModelVariant;
    model_source: 'RULES' | 'ENSEMBLE';
    active_mode: string;
    model_version: string;
    artifact_classification: string;
    prediction_horizon_days: number;
  };
  trend: {
    index_symbol: string;
    spot: number;
    dma50: number;
    dma200: number;
    above_50_dma: boolean;
    above_200_dma: boolean;
    breadth_above_50_pct: number;
    breadth_above_200_pct: number;
    realized_volatility_pct: number;
    drawdown_pct: number;
    drawdown_state: string;
  };
  factor_weather: Array<{
    factor: string;
    leadership_score: number;
    leader: string;
    note: string;
    data_quality: 'live' | 'proxy' | 'placeholder';
  }>;
  cross_asset_tone: Array<{
    asset: string;
    tone: string;
    move_pct: number;
    note: string;
    data_quality: 'live' | 'proxy' | 'placeholder';
  }>;
  sector_relative_strength: Array<{
    sector: string;
    return_1m_pct: number;
    return_3m_pct: number;
    return_6m_pct: number;
    earnings_revision_trend: string;
    note: string;
  }>;
  what_this_means_now?: {
    summary: string;
    risk_level: string;
    diversification: string;
    concentration: string;
    next_action: string;
  } | null;
  notes?: string[];
}

interface ApiMandateQuestionnaireResponse {
  investment_horizon_weeks_options: InvestmentHorizon[];
  risk_attitude_options: RiskAttitude[];
  sector_codes: string[];
  defaults: UserMandate;
}

interface ApiMarketContextResponse {
  generated_at: string;
  articles: MarketNewsArticle[];
  sector_sentiment: Record<string, number>;
  overall_market_sentiment: number;
  top_event_summary: string;
}

type FetchJsonInit = RequestInit & { timeoutMs?: number };

async function fetchJson<T>(path: string, init?: FetchJsonInit): Promise<T> {
  const { timeoutMs = 60000, ...requestInit } = init ?? {};
  const controller = new AbortController();
  const timeoutHandle = setTimeout(() => controller.abort(), timeoutMs);

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      headers: { 'Content-Type': 'application/json', ...(requestInit.headers || {}) },
      ...requestInit,
      signal: controller.signal,
    });
  } catch (error) {
    if ((error instanceof DOMException && error.name === 'AbortError') || controller.signal.aborted) {
      throw new Error(`Request timeout after ${timeoutMs}ms for ${path}`);
    }
    throw error;
  } finally {
    clearTimeout(timeoutHandle);
  }

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`API ${response.status}: ${body}`);
  }

  return response.json() as Promise<T>;
}

function toApiRiskMode(risk: RiskProfile): ApiRiskMode {
  if (risk === 'NO_RISK') return 'ULTRA_LOW';
  if (risk === 'LOW_RISK') return 'MODERATE';
  return 'HIGH';
}

function fromApiRiskMode(risk: ApiRiskMode): RiskProfile {
  if (risk === 'ULTRA_LOW') return 'NO_RISK';
  if (risk === 'MODERATE') return 'LOW_RISK';
  return 'HIGH_RISK';
}

function fromRiskAttitude(attitude: RiskAttitude): RiskProfile {
  if (attitude === 'capital_preservation') return 'NO_RISK';
  if (attitude === 'balanced') return 'LOW_RISK';
  return 'HIGH_RISK';
}

function mapRuntimeDescriptor(runtime?: {
  variant: ModelVariant;
  model_source: 'RULES' | 'ENSEMBLE';
  active_mode: string;
  model_version: string;
  artifact_classification: string;
  prediction_horizon_days: number;
}): RuntimeDescriptor {
  if (!runtime) return defaultRuntimeDescriptor();
  return {
    variant: runtime.variant,
    modelSource: runtime.model_source,
    activeMode: runtime.active_mode,
    modelVersion: runtime.model_version,
    artifactClassification: runtime.artifact_classification,
    predictionHorizonDays: runtime.prediction_horizon_days,
  };
}

function mapPortfolioFitSummary(summary?: {
  summary: string;
  risk_level: string;
  diversification: string;
  concentration: string;
  next_action: string;
} | null): PortfolioFitSummary | null {
  if (!summary) return null;
  return {
    summary: summary.summary,
    riskLevel: summary.risk_level,
    diversification: summary.diversification,
    concentration: summary.concentration,
    nextAction: summary.next_action,
  };
}

function mapStandardMetrics(metrics?: {
  return_pct: number;
  volatility_pct: number;
  sharpe_ratio: number;
  diversification_score?: number;
  correlation?: number;
  beta?: number;
}): StandardMetrics | undefined {
  if (!metrics) return undefined;
  return {
    returnPct: metrics.return_pct,
    volatilityPct: metrics.volatility_pct,
    sharpeRatio: metrics.sharpe_ratio,
    diversificationScore: metrics.diversification_score,
    correlation: metrics.correlation,
    beta: metrics.beta,
  };
}

function toApiRiskModeFromMandate(mandate?: UserMandate): ApiRiskMode {
  if (!mandate) return 'MODERATE';
  if (mandate.risk_attitude === 'capital_preservation') return 'ULTRA_LOW';
  if (mandate.risk_attitude === 'balanced') return 'MODERATE';
  return 'HIGH';
}

export async function getMandateQuestionnaireViaApi(): Promise<MandateQuestionnaire> {
  return fetchJson<ApiMandateQuestionnaireResponse>('/api/v1/portfolio/mandate/questionnaire');
}

export async function getMarketContextViaApi(): Promise<MarketContext> {
  return fetchJson<ApiMarketContextResponse>('/api/v1/news/market-context');
}

export async function getMarketDashboardViaApi(): Promise<MarketDashboard> {
  const response = await fetchJson<ApiMarketDashboardResponse>('/api/v1/market-data/regime');
  return {
    runtime: mapRuntimeDescriptor(response.runtime),
    trend: {
      indexSymbol: response.trend.index_symbol,
      spot: response.trend.spot,
      dma50: response.trend.dma50,
      dma200: response.trend.dma200,
      above50Dma: response.trend.above_50_dma,
      above200Dma: response.trend.above_200_dma,
      breadthAbove50Pct: response.trend.breadth_above_50_pct,
      breadthAbove200Pct: response.trend.breadth_above_200_pct,
      realizedVolatilityPct: response.trend.realized_volatility_pct,
      drawdownPct: response.trend.drawdown_pct,
      drawdownState: response.trend.drawdown_state,
    },
    factorWeather: response.factor_weather.map((item) => ({
      factor: item.factor,
      leadershipScore: item.leadership_score,
      leader: item.leader,
      note: item.note,
      dataQuality: item.data_quality,
    })),
    crossAssetTone: response.cross_asset_tone.map((item) => ({
      asset: item.asset,
      tone: item.tone,
      movePct: item.move_pct,
      note: item.note,
      dataQuality: item.data_quality,
    })),
    sectorRelativeStrength: response.sector_relative_strength.map((item) => ({
      sector: item.sector,
      return1mPct: item.return_1m_pct,
      return3mPct: item.return_3m_pct,
      return6mPct: item.return_6m_pct,
      earningsRevisionTrend: item.earnings_revision_trend,
      note: item.note,
    })),
    whatThisMeansNow: mapPortfolioFitSummary(response.what_this_means_now),
    notes: response.notes ?? [],
  };
}

export async function generatePortfolioViaApi(
  capitalAmount: number,
  mandate: UserMandate,
  modelVariant: ModelVariant = 'LIGHTGBM_HYBRID',
): Promise<Portfolio> {
  const response = await fetchJson<ApiGeneratePortfolioResponse>('/api/v1/portfolio/generate', {
    method: 'POST',
    timeoutMs: modelVariant === 'LIGHTGBM_HYBRID' ? 120000 : 90000,
    body: JSON.stringify({
      capital_amount: capitalAmount,
      mandate,
      model_variant: modelVariant,
    }),
  });

  const allocations = response.allocations
    .map((allocation) => {
      const stock = buildStockFromBackend(allocation);
      const backendShares = Math.max(0, Math.floor(allocation.recommended_shares ?? 0));
      const backendAmount = Number.isFinite(allocation.recommended_amount) ? allocation.recommended_amount : backendShares * stock.price;
      const fallbackTargetAmount = (capitalAmount * allocation.weight) / 100;
      const fallbackShares = Math.max(0, Math.floor(fallbackTargetAmount / stock.price));
      const shares = backendShares > 0 ? backendShares : fallbackShares;
      const amount = backendAmount > 0 ? backendAmount : shares * stock.price;
      return {
        stock,
        weight: allocation.weight,
        shares,
        amount,
        drivers: allocation.top_model_drivers ?? [],
        rationale: allocation.rationale,
        ml_pred_21d_return: allocation.ml_pred_21d_return ?? null,
        ml_pred_annual_return: allocation.ml_pred_annual_return ?? null,
        death_risk: allocation.death_risk ?? null,
        lstm_signal: allocation.lstm_signal ?? null,
        news_risk_score: allocation.news_risk_score,
        news_opportunity_score: allocation.news_opportunity_score,
        news_sentiment: allocation.news_sentiment,
        news_impact: allocation.news_impact,
        news_explanation: allocation.news_explanation,
      };
    }) as Portfolio['allocations'];

  const totalInvested = allocations.reduce((sum, allocation) => sum + allocation.amount, 0);
  const sectorCount = new Set(allocations.map((allocation) => allocation.stock.sector)).size;
  const cashRemaining = Math.max(0, capitalAmount - totalInvested);

  return {
    allocations,
    totalInvested,
    requestedCapital: capitalAmount,
    cashRemaining,
    investmentUtilizationPct: capitalAmount > 0 ? (totalInvested / capitalAmount) * 100 : 0,
    riskProfile: fromRiskAttitude(response.mandate.risk_attitude),
    mandate: response.mandate,
    backendNotes: response.notes ?? [],
    modelVariant: response.model_variant,
    modelSource: response.model_source,
    modelVersion: response.model_version,
    predictionHorizonDays: response.prediction_horizon_days,
    lookbackWindowDays: response.lookback_window_days,
    expectedHoldingPeriodDays: response.expected_holding_period_days,
    runtime: mapRuntimeDescriptor(response.runtime),
    standardMetrics: mapStandardMetrics(response.standard_metrics),
    factorExposures: response.factor_exposures ?? {},
    positionRiskContributions: (response.position_risk_contributions ?? []).map((item) => ({
      name: item.name,
      weightPct: item.weight_pct,
      contributionPct: item.contribution_pct,
      detail: item.detail,
    })),
    sectorRiskContributions: (response.sector_risk_contributions ?? []).map((item) => ({
      name: item.name,
      weightPct: item.weight_pct,
      contributionPct: item.contribution_pct,
      detail: item.detail,
    })),
    constraints: response.constraints
      ? {
          maxPositionCapPct: response.constraints.max_position_cap_pct,
          maxSectorCapPct: response.constraints.max_sector_cap_pct,
          largestPositionPct: response.constraints.largest_position_pct,
          largestPositionName: response.constraints.largest_position_name,
          largestSectorWeightPct: response.constraints.largest_sector_weight_pct,
          largestSectorName: response.constraints.largest_sector_name,
          nearPositionCap: response.constraints.near_position_cap,
          nearSectorCap: response.constraints.near_sector_cap,
        }
      : undefined,
    turnoverEstimatePct: response.turnover_estimate_pct,
    deploymentEfficiencyPct: response.deployment_efficiency_pct,
    scenarioTests: (response.scenario_tests ?? []).map((item) => ({
      name: item.name,
      pnlPct: item.pnl_pct,
      commentary: item.commentary,
    })),
    benchmarkRelative: response.benchmark_relative
      ? {
          benchmarkName: response.benchmark_relative.benchmark_name,
          activeSharePct: response.benchmark_relative.active_share_pct,
          trackingErrorPct: response.benchmark_relative.tracking_error_pct,
          exAnteAlphaPct: response.benchmark_relative.ex_ante_alpha_pct,
          informationRatio: response.benchmark_relative.information_ratio,
        }
      : undefined,
    portfolioFitSummary: mapPortfolioFitSummary(response.portfolio_fit_summary),
    metrics: {
      avgBeta: response.metrics.beta,
      estimatedAnnualReturn: response.metrics.estimated_return_pct,
      estimatedVolatility: response.metrics.estimated_volatility_pct,
      sharpeRatio: (response.metrics.estimated_return_pct - 7) / Math.max(response.metrics.estimated_volatility_pct, 1),
      divScore: Math.min(100, sectorCount * 10 + (allocations.length > 8 ? 20 : 0)),
      correlationScore: response.metrics.diversification_score,
      sectorCount,
    },
    regimeWarning: response.regime_warning || undefined,
  };
}

export async function fetchTradeIdeasViaApi(params: {
  regimeAware?: boolean;
  minChecklistScore?: number;
  maxIdeas?: number;
  portfolio?: Portfolio | null;
} = {}): Promise<TradeIdeasResponse> {
  const portfolio = params.portfolio;
  const sectorExposures = portfolio?.allocations.reduce<Record<string, number>>((acc, allocation) => {
    acc[allocation.stock.sector] = (acc[allocation.stock.sector] || 0) + allocation.weight;
    return acc;
  }, {});

  const response = await fetchJson<{
    runtime?: ApiGeneratePortfolioResponse['runtime'];
    portfolio_fit_summary?: ApiGeneratePortfolioResponse['portfolio_fit_summary'];
    notes?: string[];
    ideas: TradeIdea[];
  }>('/api/v1/trade-ideas/screen', {
    method: 'POST',
    timeoutMs: 120000,
    body: JSON.stringify({
      regime_aware: params.regimeAware ?? true,
      min_checklist_score: params.minChecklistScore ?? 7,
      max_ideas: params.maxIdeas ?? 10,
      portfolio_value: portfolio?.totalInvested || portfolio?.requestedCapital || undefined,
      cash_available: portfolio?.cashRemaining ?? undefined,
      sector_exposures: sectorExposures ?? {},
      holdings:
        portfolio?.allocations.map((allocation) => ({
          symbol: allocation.stock.symbol,
          sector: allocation.stock.sector,
          weight_pct: allocation.weight,
        })) ?? [],
    }),
  });

  return {
    runtime: mapRuntimeDescriptor(response.runtime),
    portfolioFitSummary: mapPortfolioFitSummary(response.portfolio_fit_summary),
    notes: response.notes ?? [],
    ideas: response.ideas,
  };
}

export async function analyzePortfolioViaApi(
  holdings: { symbol: string; shares: number }[],
  targetRisk: RiskProfile = 'LOW_RISK',
): Promise<AnalysisResult> {
  try {
    const response = await fetchJson<ApiAnalyzePortfolioResponse>('/api/v1/analysis/portfolio', {
      method: 'POST',
      timeoutMs: 120000,
      body: JSON.stringify({
        holdings: holdings.map((holding) => {
          const stock = ALL_STOCKS.find((candidate) => candidate.symbol === holding.symbol);
          return {
            symbol: holding.symbol,
            quantity: holding.shares,
            average_price: stock?.price,
          };
        }),
        target_risk_mode: toApiRiskMode(targetRisk),
        model_variant: 'RULES',
      }),
    });

    return {
      riskScore: response.current_beta,
      diversificationScore: response.diversification_score,
      suggestions: response.recommended_actions?.length ? response.recommended_actions : response.notes,
      rebalancingActions: response.actions.map((action) => ({
        symbol: action.symbol,
        action: action.action,
        targetWeight: action.target_weight,
        currentWeight: action.current_weight,
        reason: action.reason,
      })),
      sectorWeights: response.sector_weights,
      factorExposures: response.factor_exposures ?? {},
      correlationWarnings:
        response.correlation_risk === 'HIGH'
          ? ['High empirical correlation risk detected by the backend analyzer.']
          : response.correlation_risk === 'MODERATE'
            ? ['Moderate cross-sector correlation risk detected.']
            : [],
      totalValue: response.portfolio_value,
      totalHoldings: response.total_holdings,
      avgPairwiseCorrelation: response.avg_pairwise_correlation,
      largestSector: response.largest_sector ?? '',
      largestSectorWeight: response.largest_sector_weight ?? 0,
      healthLabel: response.health_label,
      healthSummary: response.health_summary,
      riskAssessment: response.risk_assessment,
      diversificationAssessment: response.diversification_assessment,
      concentrationAssessment: response.concentration_assessment,
      factorAssessment: response.factor_assessment,
      correlationAssessment: response.correlation_assessment,
      benchmarkAssessment: response.benchmark_assessment,
      idiosyncraticRiskAssessment: response.idiosyncratic_risk_assessment,
      rebalanceSummary: response.rebalance_summary,
      portfolioFitSummary: mapPortfolioFitSummary(response.portfolio_fit_summary),
      standardMetrics: mapStandardMetrics(response.standard_metrics),
      recommendedActions: response.recommended_actions ?? [],
      backendNotes: response.notes,
      modelVariantApplied: response.model_variant_applied,
      modelSource: response.model_source ?? 'RULES',
      activeMode: response.active_mode ?? 'rules_only',
      modelVersion: response.model_version ?? 'rules',
      artifactClassification: response.artifact_classification ?? 'missing',
      runtime: response.runtime ? mapRuntimeDescriptor(response.runtime) : undefined,
      holdingPeriodDaysRecommended: response.holding_period_days_recommended,
      predictionHorizonDays: response.prediction_horizon_days,
      holdingPeriodReason: response.holding_period_reason,
      mlPredictions: response.ml_predictions ?? {},
      topModelDriversBySymbol: response.top_model_drivers_by_symbol ?? {},
    };
  } catch (error) {
    const fallback = analyzePortfolio(holdings);
    return {
      ...fallback,
      backendNotes: [
        `Using local holdings analyzer because the backend analysis request failed: ${error instanceof Error ? error.message : 'unknown error'}.`,
      ],
      modelVariantApplied: 'RULES',
      modelSource: 'RULES',
      activeMode: 'local_fallback',
      modelVersion: 'local-rules',
      artifactClassification: 'fallback',
      holdingPeriodDaysRecommended: 21,
      predictionHorizonDays: 21,
      holdingPeriodReason: 'Fallback analysis uses local price metadata and should be treated as an approximate review.',
      runtime: defaultRuntimeDescriptor(),
      standardMetrics: {
        returnPct: 0,
        volatilityPct: 0,
        sharpeRatio: 0,
        diversificationScore: fallback.diversificationScore,
        beta: fallback.riskScore,
      },
      mlPredictions: {},
      topModelDriversBySymbol: {},
    };
  }
}

export async function runBacktestViaApi(
  portfolio: Portfolio,
  config: BacktestConfig,
  modelVariant: ModelVariant = 'LIGHTGBM_HYBRID',
): Promise<BacktestResult> {
  const response = await fetchJson<ApiBacktestResponse>('/api/v1/backtests/run', {
    method: 'POST',
    body: JSON.stringify({
      strategy_name: 'nse-ai-portfolio',
      start_date: config.startDate,
      end_date: config.endDate,
      risk_mode: toApiRiskModeFromMandate(portfolio.mandate as UserMandate | undefined),
      mandate: portfolio.mandate ?? null,
      capital_amount: portfolio.totalInvested,
      rebalance_frequency: config.rebalanceFreq.toUpperCase(),
      stop_loss_pct: config.stopLossPct,
      take_profit_pct: config.takeProfitPct,
      model_variant: modelVariant,
    }),
  });

  return {
    equityCurve: response.equity_curve.map((point) => ({
      date: point.date,
      value: point.portfolio_value,
      benchmark: point.benchmark_value,
    })),
    finalValue: response.metrics.final_value,
    totalReturn: response.metrics.total_return_pct,
    cagr: response.metrics.cagr_pct,
    maxDrawdown: response.metrics.max_drawdown_pct,
    sharpe: response.metrics.sharpe_ratio,
    sortino: response.metrics.sortino_ratio,
    calmar: response.metrics.calmar_ratio,
    winRate: response.metrics.win_rate_pct,
    turnoverPct: response.metrics.turnover_pct,
    totalTrades: response.metrics.total_trades,
    taxLiability: {
      stcgGain: response.tax_liability.stcg_gain,
      ltcgGain: response.tax_liability.ltcg_gain,
      stcgTax: response.tax_liability.stcg_tax,
      ltcgTax: response.tax_liability.ltcg_tax,
      cessTax: response.tax_liability.cess_tax,
      totalTax: response.tax_liability.total_tax,
    },
    costBreakdown: {
      totalBrokerage: response.cost_breakdown.total_brokerage,
      totalSTT: response.cost_breakdown.total_stt,
      totalStampDuty: response.cost_breakdown.total_stamp_duty,
      totalExchangeTxn: response.cost_breakdown.total_exchange_txn,
      totalSebiFees: response.cost_breakdown.total_sebi_fees,
      totalGST: response.cost_breakdown.total_gst,
      totalSlippage: response.cost_breakdown.total_slippage,
      totalCosts: response.cost_breakdown.total_costs,
    },
    config,
    initialInvestment: response.metrics.initial_investment,
    notes: response.notes ?? [],
    modelVariant: response.model_variant,
    modelSource: response.model_source,
    modelVersion: response.model_version,
    predictionHorizonDays: response.prediction_horizon_days,
    topModelDriversBySymbol: response.top_model_drivers_by_symbol ?? {},
  };
}

export async function getBenchmarkComparisonViaApi(): Promise<ComparisonResult> {
  try {
    const response = await fetchJson<ApiBenchmarkResponse>('/api/v1/benchmarks/summary', {
      timeoutMs: 120000,
    });
    const strategies: BenchmarkStrategy[] = response.strategies.map((strategy) => ({
      name: strategy.name,
      description: strategy.description,
      constructionMethod: strategy.construction_method,
      isProxy: strategy.is_proxy,
      sourceWindow: strategy.source_window,
      constituentMethod: strategy.constituent_method,
      limitations: strategy.limitations ?? [],
      annualReturn: strategy.annual_return_pct,
      volatility: strategy.volatility_pct,
      maxDrawdown: strategy.max_drawdown_pct,
      sharpe: strategy.sharpe_ratio,
      sortino: strategy.sortino_ratio,
      cagr5Y: strategy.cagr_5y_pct,
      expenseRatio: strategy.expense_ratio_pct,
      type: strategy.category,
      sourceType: strategy.source_type,
      sourceProvider: strategy.source_provider,
      relativeAccuracyScorePct: strategy.relative_accuracy_score_pct,
    }));

    const projectedGrowth = response.projected_growth.map((row) => ({
      year: row.year,
      ...row.values,
    }));

    const winner = strategies.reduce((best, current) => (current.sharpe > best.sharpe ? current : best)).name;
    return { strategies, projectedGrowth, winner, notes: response.notes ?? [] };
  } catch (error) {
    const fallback = getComparisonResult(500000);
    return {
      ...fallback,
      notes: [
        ...(fallback.notes ?? []),
        `Using local comparison fallback because the benchmark API failed: ${error instanceof Error ? error.message : 'unknown error'}.`,
      ],
    };
  }
}

export async function getBenchmarkCompareViaApi(portfolio: Portfolio | null): Promise<BenchmarkCompareResponse> {
  const response = await fetchJson<ApiBenchmarkCompareResponse>('/api/v1/benchmarks/compare', {
    method: 'POST',
    timeoutMs: 120000,
    body: JSON.stringify({
      capital_amount: portfolio?.requestedCapital ?? portfolio?.totalInvested ?? undefined,
      mandate: portfolio?.mandate ?? undefined,
      allocations:
        portfolio?.allocations.map((allocation) => ({
          symbol: allocation.stock.symbol,
          weight_pct: allocation.weight,
        })) ?? [],
      model_variant: portfolio?.modelVariant ?? undefined,
    }),
  });

  return {
    runtime: mapRuntimeDescriptor(response.runtime),
    portfolioFitSummary: mapPortfolioFitSummary(response.portfolio_fit_summary),
    benchmarkMatchSummary: response.benchmark_match_summary,
    strategies: response.strategies.map((strategy) => ({
      strategyName: strategy.strategy_name,
      annualReturnPct: strategy.annual_return_pct,
      volatilityPct: strategy.volatility_pct,
      sharpeRatio: strategy.sharpe_ratio,
      maxDrawdownPct: strategy.max_drawdown_pct,
      trackingErrorPct: strategy.tracking_error_pct,
      informationRatio: strategy.information_ratio,
      downsideCapturePct: strategy.downside_capture_pct,
      upsideCapturePct: strategy.upside_capture_pct,
      drawdownDurationDays: strategy.drawdown_duration_days,
      recoveryDays: strategy.recovery_days,
      activeSharePct: strategy.active_share_pct,
      netOfCostReturnPct: strategy.net_of_cost_return_pct,
      netOfTaxReturnPct: strategy.net_of_tax_return_pct,
      exAnteAlphaPct: strategy.ex_ante_alpha_pct,
      benchmarkName: strategy.benchmark_name,
      matchedOn: strategy.matched_on,
    })),
    series: response.series.map((point) => ({
      date: point.date,
      strategyReturns: point.strategy_returns,
      rollingExcessReturn: point.rolling_excess_return,
      rollingSharpe: point.rolling_sharpe,
    })),
    notes: response.notes ?? [],
  };
}

export async function getObservabilityKpisViaApi(): Promise<ApiObservabilityKpiResponse> {
  return fetchJson<ApiObservabilityKpiResponse>('/api/v1/observability/kpis', {
    timeoutMs: 120000,
  });
}

export async function getCurrentModelStatusViaApi(): Promise<CurrentModelStatus> {
  const response = await fetchJson<ApiCurrentModelStatusResponse>('/api/v1/models/current');
  return {
    available: response.available,
    variant: response.variant,
    modelVersion: response.model_version,
    predictionHorizonDays: response.prediction_horizon_days,
    trainingMode: response.training_mode,
    artifactClassification: response.artifact_classification,
    validationMetrics: response.validation_metrics,
    validationSummary: response.validation_summary,
    trainingMetadata: response.training_metadata,
    evaluationReport: response.evaluation_report,
    runtimeSitePackages: response.runtime_site_packages,
    reason: response.reason,
    notes: response.notes ?? [],
    healthScorePct: response.health_score_pct,
    currentSignalsAsOfDate: response.current_signals_as_of_date,
    currentSignals: (response.current_signals ?? []).map((signal) => ({
      symbol: signal.symbol,
      sector: signal.sector,
      action: signal.action,
      confidence: signal.confidence,
      predictedReturn21dPct: signal.predicted_return_21d_pct,
      predictedAnnualReturnPct: signal.predicted_annual_return_pct,
      topDrivers: signal.top_drivers ?? [],
    })),
    validationOverview: response.validation_overview
      ? {
          available: response.validation_overview.available,
          modelVersion: response.validation_overview.model_version,
          trainingMode: response.validation_overview.training_mode,
          predictionHorizonDays: response.validation_overview.prediction_horizon_days,
          selectionStatus: response.validation_overview.selection_status,
          foldCount: response.validation_overview.fold_count,
          sampleCount: response.validation_overview.sample_count,
          oosSharpeRatio: response.validation_overview.oos_sharpe_ratio,
          informationCoefficient: response.validation_overview.information_coefficient,
          hitRatePct: response.validation_overview.hit_rate_pct,
          avgTopBottomSpreadPct: response.validation_overview.avg_top_bottom_spread_pct,
          walkForwardEquityCurve: (response.validation_overview.walk_forward_equity_curve ?? []).map((point) => ({
            date: point.date,
            equityIndex: point.equity_index,
            periodReturnPct: point.period_return_pct,
            informationCoefficient: point.information_coefficient,
            hitRatePct: point.hit_rate_pct,
            sampleCount: point.sample_count,
          })),
          notes: response.validation_overview.notes ?? [],
        }
      : undefined,
  };
}

export async function getMarketDataSummaryViaApi(): Promise<MarketDataSummary> {
  const response = await fetchJson<ApiMarketDataSummaryResponse>('/api/v1/market-data/summary');
  return {
    available: response.available,
    minTradeDate: response.min_trade_date,
    maxTradeDate: response.max_trade_date,
    dailyBarCount: response.daily_bar_count,
    instrumentCount: response.instrument_count,
    sessionStatus: response.session_status
      ? {
          exchange: response.session_status.exchange,
          timezone: response.session_status.timezone,
          status: response.session_status.status,
          label: response.session_status.label,
          reason: response.session_status.reason,
          isTradingDay: response.session_status.is_trading_day,
          sessionDate: response.session_status.session_date,
          currentTime: response.session_status.current_time,
          nextOpenAt: response.session_status.next_open_at,
          nextCloseAt: response.session_status.next_close_at,
          holidayName: response.session_status.holiday_name,
          calendarSource: response.session_status.calendar_source,
        }
      : undefined,
    notes: response.notes ?? [],
  };
}

function buildStockFromBackend(allocation: ApiGeneratePortfolioResponse['allocations'][number]): Stock {
  const localStock = ALL_STOCKS.find((candidate) => candidate.symbol === allocation.symbol);
  if (localStock) {
    return {
      ...localStock,
      name: allocation.name || localStock.name,
      sector: allocation.sector || localStock.sector,
      price: allocation.latest_price || localStock.price,
    };
  }

  return {
    symbol: allocation.symbol,
    name: allocation.name || allocation.symbol,
    sector: allocation.sector || 'Unknown',
    price: allocation.latest_price || 1,
    beta: 1,
    dividendYield: 0,
    marketCap: 'Large',
    pe: 0,
    pbv: 0,
    high52w: allocation.latest_price || 1,
    low52w: allocation.latest_price || 1,
    momentum6M: 0,
  };
}
