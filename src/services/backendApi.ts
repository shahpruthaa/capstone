import { LIQUID_ASSETS, NSE_STOCKS } from '../data/stocks';
import type { ComparisonResult, BenchmarkStrategy } from './benchmarkService';
import type { BacktestConfig, BacktestResult } from './backtestEngine';
import type {
  AnalysisResult,
  Portfolio,
  RiskProfile,
} from './portfolioService';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const API_TIMEOUT_MS = 10_000;
const BENCHMARK_API_TIMEOUT_MS = 60_000;
const ALL_STOCKS = [...NSE_STOCKS, ...LIQUID_ASSETS];

type ApiRiskMode = 'ULTRA_LOW' | 'MODERATE' | 'HIGH';
export type ModelVariant = 'RULES' | 'LIGHTGBM_HYBRID';

export interface CurrentModelStatus {
  available: boolean;
  variant: ModelVariant;
  modelSource?: 'RULES' | 'LIGHTGBM' | 'ENSEMBLE';
  activeMode?: string;
  modelVersion?: string;
  predictionHorizonDays?: number;
  trainingMode?: string;
  artifactClassification?: 'bootstrap' | 'standard' | 'missing';
  validationMetrics?: Record<string, unknown>;
  validationSummary?: Record<string, unknown>;
  trainingMetadata?: Record<string, unknown>;
  evaluationReport?: Record<string, unknown>;
  components?: Record<string, unknown>;
  availableComponents?: string[];
  missingComponents?: string[];
  groqConnected?: boolean;
  groqModel?: string;
  notes?: string[];
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

interface ApiGeneratePortfolioResponse {
  model_variant: ModelVariant;
  model_source: 'RULES' | 'LIGHTGBM' | 'ENSEMBLE';
  model_version: string;
  prediction_horizon_days: number;
  active_mode?: string;
  artifact_classification?: string;
  risk_mode: ApiRiskMode;
  investment_amount: number;
  allocations: { symbol: string; sector: string; weight: number; rationale: string; top_model_drivers?: string[] }[];
  metrics: {
    estimated_return_pct: number;
    estimated_volatility_pct: number;
    beta: number;
    diversification_score: number;
  };
  holding_period_days_recommended?: number;
  holding_period_reason?: string;
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
  model_source?: 'RULES' | 'LIGHTGBM' | 'ENSEMBLE';
  model_version?: string;
  prediction_horizon_days?: number;
  active_mode?: string;
  artifact_classification?: string;
  ml_predictions?: Record<string, number>;
  top_model_drivers_by_symbol?: Record<string, string[]>;
  holding_period_days_recommended?: number;
  holding_period_reason?: string;
  notes: string[];
}

interface ApiBacktestResponse {
  model_variant: ModelVariant;
  model_source: 'RULES' | 'LIGHTGBM' | 'ENSEMBLE';
  model_version: string;
  prediction_horizon_days: number;
  active_mode?: string;
  artifact_classification?: string;
  top_model_drivers_by_symbol?: Record<string, string[]>;
  validation_as_of_date?: string;
  validation_horizon_days?: number;
  validation_samples?: number;
  validation_hit_rate_pct?: number;
  validation_mae_pct?: number;
  prediction_validation?: {
    symbol: string;
    predicted_return_pct: number;
    actual_return_pct: number;
    absolute_error_pct: number;
    direction_match: boolean;
  }[];
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

interface ApiCurrentModelStatusResponse {
  available: boolean;
  variant: ModelVariant;
  model_source?: 'RULES' | 'LIGHTGBM' | 'ENSEMBLE';
  active_mode?: string;
  model_version?: string;
  prediction_horizon_days?: number;
  training_mode?: string;
  artifact_classification?: 'bootstrap' | 'standard' | 'missing';
  validation_metrics?: Record<string, unknown>;
  validation_summary?: Record<string, unknown>;
  training_metadata?: Record<string, unknown>;
  evaluation_report?: Record<string, unknown>;
  components?: Record<string, unknown>;
  available_components?: string[];
  missing_components?: string[];
  groq_connected?: boolean;
  groq_model?: string;
  notes?: string[];
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

interface ApiChatResponse {
  response: string;
}

interface ApiPortfolioExplainResponse {
  explanation: string;
}

interface ExplainPortfolioAllocation {
  symbol: string;
  sector: string;
  weight: number;
  rationale?: string;
  top_model_drivers?: string[];
}

let cachedModelStatus: { value: CurrentModelStatus; fetchedAt: number } | null = null;
let cachedMarketSummary: { value: MarketDataSummary; fetchedAt: number } | null = null;
const STATUS_CACHE_TTL_MS = 30_000;

async function fetchJson<T>(
  path: string,
  init?: RequestInit,
  options?: { timeoutMs?: number },
): Promise<T> {
  const controller = new AbortController();
  const timeoutMs = options?.timeoutMs ?? API_TIMEOUT_MS;
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
    signal: controller.signal,
    ...init,
  }).finally(() => {
    clearTimeout(timeout);
  });

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

export async function generatePortfolioViaApi(amount: number, risk: RiskProfile, modelVariant: ModelVariant = 'LIGHTGBM_HYBRID'): Promise<Portfolio> {
  const response = await fetchJson<ApiGeneratePortfolioResponse>('/api/v1/portfolio/generate', {
    method: 'POST',
    body: JSON.stringify({
      investment_amount: amount,
      risk_mode: toApiRiskMode(risk),
      model_variant: modelVariant,
    }),
  });

  const allocations = response.allocations
    .map((allocation) => {
      const stock = ALL_STOCKS.find((candidate) => candidate.symbol === allocation.symbol);
      if (!stock) return null;
      const stockAmount = (amount * allocation.weight) / 100;
      const shares = Math.max(1, Math.floor(stockAmount / stock.price));
      return {
        stock,
        weight: allocation.weight,
        shares,
        amount: shares * stock.price,
        drivers: allocation.top_model_drivers ?? [],
      };
    })
    .filter(Boolean) as Portfolio['allocations'];

  const totalInvested = allocations.reduce((sum, allocation) => sum + allocation.amount, 0);
  const sectorCount = new Set(allocations.map((allocation) => allocation.stock.sector)).size;

  return {
    allocations,
    totalInvested,
    riskProfile: fromApiRiskMode(response.risk_mode),
    backendNotes: response.notes ?? [],
    modelVariant: response.model_variant,
    modelSource: response.model_source,
    modelVersion: response.model_version,
    predictionHorizonDays: response.prediction_horizon_days,
    activeMode: response.active_mode,
    artifactClassification: response.artifact_classification,
    holdingPeriodDaysRecommended: response.holding_period_days_recommended,
    holdingPeriodReason: response.holding_period_reason,
    metrics: {
      avgBeta: response.metrics.beta,
      estimatedAnnualReturn: response.metrics.estimated_return_pct,
      estimatedVolatility: response.metrics.estimated_volatility_pct,
      sharpeRatio: (response.metrics.estimated_return_pct - 7) / Math.max(response.metrics.estimated_volatility_pct, 1),
      divScore: Math.min(100, sectorCount * 10 + (allocations.length > 8 ? 20 : 0)),
      correlationScore: response.metrics.diversification_score,
      sectorCount,
    },
  };
}

export async function analyzePortfolioViaApi(
  holdings: { symbol: string; shares: number }[],
  targetRisk: RiskProfile = 'LOW_RISK',
): Promise<AnalysisResult> {
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
    modelSource: response.model_source,
    modelVersion: response.model_version,
    predictionHorizonDays: response.prediction_horizon_days,
    activeMode: response.active_mode,
    artifactClassification: response.artifact_classification,
    mlPredictions: response.ml_predictions ?? {},
    topModelDriversBySymbol: response.top_model_drivers_by_symbol ?? {},
    holdingPeriodDaysRecommended: response.holding_period_days_recommended,
    holdingPeriodReason: response.holding_period_reason,
  };
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
      risk_mode: toApiRiskMode(portfolio.riskProfile),
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
    activeMode: response.active_mode,
    artifactClassification: response.artifact_classification,
    topModelDriversBySymbol: response.top_model_drivers_by_symbol ?? {},
    validationAsOfDate: response.validation_as_of_date,
    validationHorizonDays: response.validation_horizon_days ?? 21,
    validationSamples: response.validation_samples ?? 0,
    validationHitRatePct: response.validation_hit_rate_pct ?? 0,
    validationMaePct: response.validation_mae_pct ?? 0,
    predictionValidation: (response.prediction_validation ?? []).map((row) => ({
      symbol: row.symbol,
      predictedReturnPct: row.predicted_return_pct,
      actualReturnPct: row.actual_return_pct,
      absoluteErrorPct: row.absolute_error_pct,
      directionMatch: row.direction_match,
    })),
  };
}

export async function getBenchmarkComparisonViaApi(): Promise<ComparisonResult> {
  const response = await fetchJson<ApiBenchmarkResponse>(
    '/api/v1/benchmarks/summary',
    undefined,
    { timeoutMs: BENCHMARK_API_TIMEOUT_MS },
  );
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
    sourceType: strategy.source_type ?? 'LOCAL_PROXY',
    sourceProvider: strategy.source_provider ?? 'local_research',
    relativeAccuracyScorePct: strategy.relative_accuracy_score_pct ?? 0,
  }));

  const projectedGrowth = response.projected_growth.map((row) => ({
    year: row.year,
    ...row.values,
  }));

  const winner = strategies.reduce((best, current) => (current.sharpe > best.sharpe ? current : best)).name;
  return { strategies, projectedGrowth, winner, notes: response.notes ?? [] };
}

export async function getCurrentModelStatusViaApi(): Promise<CurrentModelStatus> {
  if (cachedModelStatus && Date.now() - cachedModelStatus.fetchedAt < STATUS_CACHE_TTL_MS) {
    return cachedModelStatus.value;
  }
  const response = await fetchJson<ApiCurrentModelStatusResponse>('/api/v1/models/current');
  const mapped: CurrentModelStatus = {
    available: response.available,
    variant: response.variant,
    modelSource: response.model_source,
    activeMode: response.active_mode,
    modelVersion: response.model_version,
    predictionHorizonDays: response.prediction_horizon_days,
    trainingMode: response.training_mode,
    artifactClassification: response.artifact_classification,
    validationMetrics: response.validation_metrics,
    validationSummary: response.validation_summary,
    trainingMetadata: response.training_metadata,
    evaluationReport: response.evaluation_report,
    components: response.components,
    availableComponents: response.available_components,
    missingComponents: response.missing_components,
    groqConnected: response.groq_connected,
    groqModel: response.groq_model,
    notes: response.notes,
    runtimeSitePackages: response.runtime_site_packages,
    reason: response.reason,
  };
  cachedModelStatus = { value: mapped, fetchedAt: Date.now() };
  return mapped;
}

export async function getMarketDataSummaryViaApi(): Promise<MarketDataSummary> {
  if (cachedMarketSummary && Date.now() - cachedMarketSummary.fetchedAt < STATUS_CACHE_TTL_MS) {
    return cachedMarketSummary.value;
  }
  const response = await fetchJson<ApiMarketDataSummaryResponse>('/api/v1/market-data/summary');
  const mapped: MarketDataSummary = {
    available: response.available,
    minTradeDate: response.min_trade_date,
    maxTradeDate: response.max_trade_date,
    dailyBarCount: response.daily_bar_count,
    instrumentCount: response.instrument_count,
    notes: response.notes ?? [],
  };
  cachedMarketSummary = { value: mapped, fetchedAt: Date.now() };
  return mapped;
}

export async function explainPortfolioViaApi(payload: {
  allocations: ExplainPortfolioAllocation[];
  riskMode: string;
  totalAmount: number;
}): Promise<string> {
  const response = await fetchJson<ApiPortfolioExplainResponse>('/api/v1/explain/portfolio', {
    method: 'POST',
    body: JSON.stringify({
      allocations: payload.allocations,
      risk_mode: payload.riskMode,
      total_amount: payload.totalAmount,
    }),
  });
  return response.explanation;
}

export async function chatWithAssistantViaApi(payload: {
  message: string;
  history: Array<{ role: 'assistant' | 'user'; content: string }>;
}): Promise<string> {
  const response = await fetchJson<ApiChatResponse>('/api/v1/explain/chat', {
    method: 'POST',
    body: JSON.stringify({
      message: payload.message,
      history: payload.history,
    }),
  });
  return response.response;
}
