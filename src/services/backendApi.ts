import { LIQUID_ASSETS, NSE_STOCKS, Stock } from '../data/stocks';
import { ComparisonResult, BenchmarkStrategy, getComparisonResult } from './benchmarkService';
import { BacktestConfig, BacktestResult } from './backtestEngine';
import {
  AnalysisResult,
  Portfolio,
  RiskProfile,
  analyzePortfolio,
} from './portfolioService';

const viteEnv = (import.meta as ImportMeta & { env?: Record<string, string | undefined> }).env;
export const API_BASE_URL = viteEnv?.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
const ALL_STOCKS = [...NSE_STOCKS, ...LIQUID_ASSETS];

type ApiRiskMode = 'ULTRA_LOW' | 'MODERATE' | 'HIGH';
export type ModelVariant = 'RULES' | 'LIGHTGBM_HYBRID';
export type RiskAttitude = 'capital_preservation' | 'balanced' | 'growth';
export type InvestmentHorizon = '2-4' | '4-8' | '8-24';

export interface UserMandate {
  investment_horizon_weeks: InvestmentHorizon;
  max_portfolio_drawdown_pct: number;
  max_position_size_pct: number;
  preferred_num_positions: number;
  sector_inclusions: string[];
  sector_exclusions: string[];
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
}

export interface MarketDataSummary {
  available: boolean;
  minTradeDate?: string;
  maxTradeDate?: string;
  dailyBarCount: number;
  instrumentCount: number;
  notes: string[];
}

export interface TradeIdeaCheck {
  passed: boolean;
  score: number;
  reason: string;
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
  max_loss_per_unit: number;
  regime_alignment: string;
  sector_rank: number;
  catalyst?: string | null;
}

interface ApiGeneratePortfolioResponse {
  model_variant: ModelVariant;
  model_source: 'RULES' | 'LIGHTGBM';
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
  regime_warning?: string | null;
  notes?: string[];
}

interface ApiAnalyzePortfolioResponse {
  portfolio_value: number;
  current_beta: number;
  diversification_score: number;
  sector_weights: Record<string, number>;
  factor_exposures?: Record<string, number>;
  correlation_risk: 'LOW' | 'MODERATE' | 'HIGH';
  actions: { symbol: string; action: 'BUY' | 'SELL' | 'HOLD'; target_weight: number; current_weight: number; reason: string }[];
  model_variant_applied: ModelVariant;
  model_source?: 'RULES' | 'LIGHTGBM';
  active_mode?: string;
  model_version?: string;
  artifact_classification?: string;
  prediction_horizon_days?: number;
  ml_predictions?: Record<string, number>;
  top_model_drivers_by_symbol?: Record<string, string[]>;
  holding_period_days_recommended?: number;
  holding_period_reason?: string;
  notes: string[];
}

interface ApiBacktestResponse {
  model_variant: ModelVariant;
  model_source: 'RULES' | 'LIGHTGBM';
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
}

interface ApiMarketDataSummaryResponse {
  available: boolean;
  min_trade_date?: string;
  max_trade_date?: string;
  daily_bar_count: number;
  instrument_count: number;
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

function isRequestTimeoutError(error: unknown): boolean {
  return error instanceof Error && /timeout/i.test(error.message);
}

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

export async function generatePortfolioViaApi(
  capitalAmount: number,
  mandate: UserMandate,
  modelVariant: ModelVariant = 'LIGHTGBM_HYBRID',
): Promise<Portfolio> {
  const localNotes: string[] = [];
  let response: ApiGeneratePortfolioResponse;

  try {
    response = await fetchJson<ApiGeneratePortfolioResponse>('/api/v1/portfolio/generate', {
      method: 'POST',
      timeoutMs: modelVariant === 'LIGHTGBM_HYBRID' ? 120000 : 90000,
      body: JSON.stringify({
        capital_amount: capitalAmount,
        mandate,
        model_variant: modelVariant,
      }),
    });
  } catch (error) {
    if (modelVariant !== 'LIGHTGBM_HYBRID' || !isRequestTimeoutError(error)) {
      throw error;
    }

    localNotes.push('LightGBM hybrid request timed out; automatically retried with rule-based allocator for responsiveness.');
    response = await fetchJson<ApiGeneratePortfolioResponse>('/api/v1/portfolio/generate', {
      method: 'POST',
      timeoutMs: 90000,
      body: JSON.stringify({
        capital_amount: capitalAmount,
        mandate,
        model_variant: 'RULES' as ModelVariant,
      }),
    });
  }

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
    backendNotes: [...localNotes, ...(response.notes ?? [])],
    modelVariant: response.model_variant,
    modelSource: response.model_source,
    modelVersion: response.model_version,
    predictionHorizonDays: response.prediction_horizon_days,
    lookbackWindowDays: response.lookback_window_days,
    expectedHoldingPeriodDays: response.expected_holding_period_days,
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
} = {}): Promise<TradeIdea[]> {
  const query = new URLSearchParams();
  query.set('regime_aware', String(params.regimeAware ?? true));
  query.set('min_checklist_score', String(params.minChecklistScore ?? 7));
  query.set('max_ideas', String(params.maxIdeas ?? 10));
  return fetchJson<TradeIdea[]>(`/api/v1/trade-ideas?${query.toString()}`);
}

export async function analyzePortfolioViaApi(
  holdings: { symbol: string; shares: number }[],
  targetRisk: RiskProfile = 'LOW_RISK',
): Promise<AnalysisResult> {
  try {
    const response = await fetchJson<ApiAnalyzePortfolioResponse>('/api/v1/analysis/portfolio', {
      method: 'POST',
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
      }),
    });

    return {
      riskScore: response.current_beta,
      diversificationScore: response.diversification_score,
      suggestions: response.notes,
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
      backendNotes: response.notes,
      modelVariantApplied: response.model_variant_applied,
      modelSource: response.model_source ?? 'RULES',
      activeMode: response.active_mode ?? 'rules_only',
      modelVersion: response.model_version ?? 'rules',
      artifactClassification: response.artifact_classification ?? 'missing',
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
    notes: response.notes ?? [],
  };
}

export type ExplainChatHistoryItem = { role: 'assistant' | 'user'; content: string };

export async function fetchPlatformContext(): Promise<Record<string, unknown>> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/explain/context`);
    if (!response.ok) return {};
    return await response.json();
  } catch {
    return {};
  }
}

export async function postExplainChat(message: string, history: ExplainChatHistoryItem[], portfolioContext: Record<string, unknown> = {}): Promise<{ response: string; action?: { name: string; arguments: any } }> {
  const response = await fetch(`${API_BASE_URL}/api/v1/explain/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, history, portfolio_context: portfolioContext }),
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`API ${response.status}: ${body}`);
  }
  return response.json() as Promise<{ response: string }>;
}

export async function postExplainPortfolio(portfolio: Portfolio): Promise<{ explanation: string }> {
  const response = await fetch(`${API_BASE_URL}/api/v1/explain/portfolio`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      allocations: portfolio.allocations.map((a) => ({
        symbol: a.stock.symbol,
        sector: a.stock.sector,
        weight: a.weight,
        rationale: a.rationale ?? '',
        top_model_drivers: a.drivers ?? [],
        ml_pred_21d_return: a.ml_pred_21d_return ?? null,
        ml_pred_annual_return: a.ml_pred_annual_return ?? null,
        death_risk: a.death_risk ?? null,
        lstm_signal: a.lstm_signal ?? null,
      })),
      risk_mode: toApiRiskModeFromMandate(portfolio.mandate as UserMandate | undefined),
      total_amount: portfolio.totalInvested || 500000,
    }),
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`API ${response.status}: ${body}`);
  }
  return response.json() as Promise<{ explanation: string }>;
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

export async function getMarketEventsAnalysis(): Promise<{ analysis: string; generated_at: string }> {
  const response = await fetch(`${API_BASE_URL}/api/v1/explain/market-events`);
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`API ${response.status}: ${body}`);
  }
  return response.json() as Promise<{ analysis: string; generated_at: string }>;
}

export async function postPortfolioRebalancing(portfolio: Portfolio): Promise<{
  overall_assessment: string;
  risk_adjustment: string;
  timeline: string;
  explanation: string;
  recommendations: Array<{
    action: string;
    symbol: string;
    current_weight: number;
    target_weight: number;
    rationale: string;
    urgency: string;
    expected_impact: string;
  }>;
}> {
  const response = await fetch(`${API_BASE_URL}/api/v1/explain/portfolio/rebalance`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      allocations: portfolio.allocations.map((a) => ({
        symbol: a.stock.symbol,
        sector: a.stock.sector,
        weight: a.weight,
        rationale: a.rationale ?? '',
        top_model_drivers: a.drivers ?? [],
        ml_pred_21d_return: a.ml_pred_21d_return ?? null,
        ml_pred_annual_return: a.ml_pred_annual_return ?? null,
        death_risk: a.death_risk ?? null,
        lstm_signal: a.lstm_signal ?? null,
      })),
      risk_mode: toApiRiskModeFromMandate(portfolio.mandate as UserMandate | undefined),
      total_amount: portfolio.totalInvested || 500000,
    }),
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`API ${response.status}: ${body}`);
  }
  return response.json() as Promise<{
    overall_assessment: string;
    risk_adjustment: string;
    timeline: string;
    explanation: string;
    recommendations: Array<{
      action: string;
      symbol: string;
      current_weight: number;
      target_weight: number;
      rationale: string;
      urgency: string;
      expected_impact: string;
    }>;
  }>;
}
