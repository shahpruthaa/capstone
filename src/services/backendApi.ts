import { LIQUID_ASSETS, NSE_STOCKS } from '../data/stocks';
import { ComparisonResult, BenchmarkStrategy } from './benchmarkService';
import { BacktestConfig, BacktestResult } from './backtestEngine';
import {
  AnalysisResult,
  Portfolio,
  RiskProfile,
} from './portfolioService';

const viteEnv = (import.meta as ImportMeta & { env?: Record<string, string | undefined> }).env;
export const API_BASE_URL = viteEnv?.VITE_API_BASE_URL || 'http://localhost:8000';
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
  briefing: string;
  actionableTakeaways: string[];
  summarySource: 'llm' | 'rules';
}

export type CopilotActionType = 'generate_portfolio' | 'run_backtest' | 'load_trade_ideas' | 'refresh_market';

export interface CopilotAction {
  type: CopilotActionType;
  label: string;
  auto_execute: boolean;
  blocked_reason?: string | null;
  params?: Record<string, unknown>;
}

export interface CopilotChatResponse {
  response: string;
  action?: CopilotAction | null;
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
    sector: string;
    weight: number;
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
  ml_predictions?: Record<string, number>;
  top_model_drivers_by_symbol?: Record<string, string[]>;
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
  }[];
  projected_growth: { year: number; values: Record<string, number> }[];
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
  briefing: string;
  actionable_takeaways?: string[];
  summary_source?: 'llm' | 'rules';
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
    ...init,
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
  const response = await fetchJson<ApiMarketContextResponse>('/api/v1/news/market-context');
  return {
    generated_at: response.generated_at,
    articles: response.articles,
    sector_sentiment: response.sector_sentiment,
    overall_market_sentiment: response.overall_market_sentiment,
    top_event_summary: response.top_event_summary,
    briefing: response.briefing,
    actionableTakeaways: response.actionable_takeaways ?? [],
    summarySource: response.summary_source ?? 'rules',
  };
}

export async function generatePortfolioViaApi(
  capitalAmount: number,
  mandate: UserMandate,
  modelVariant: ModelVariant = 'LIGHTGBM_HYBRID',
): Promise<Portfolio> {
  const response = await fetchJson<ApiGeneratePortfolioResponse>('/api/v1/portfolio/generate', {
    method: 'POST',
    body: JSON.stringify({
      capital_amount: capitalAmount,
      mandate,
      model_variant: modelVariant,
    }),
  });

  const allocations = response.allocations
    .map((allocation) => {
      const stock = ALL_STOCKS.find((candidate) => candidate.symbol === allocation.symbol);
      if (!stock) return null;
      const stockAmount = (capitalAmount * allocation.weight) / 100;
      const shares = Math.max(1, Math.floor(stockAmount / stock.price));
      return {
        stock,
        weight: allocation.weight,
        shares,
        amount: shares * stock.price,
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
    })
    .filter(Boolean) as Portfolio['allocations'];

  const totalInvested = allocations.reduce((sum, allocation) => sum + allocation.amount, 0);
  const sectorCount = new Set(allocations.map((allocation) => allocation.stock.sector)).size;

  return {
    allocations,
    totalInvested,
    riskProfile: fromRiskAttitude(response.mandate.risk_attitude),
    mandate: response.mandate,
    backendNotes: response.notes ?? [],
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
    mlPredictions: response.ml_predictions ?? {},
    topModelDriversBySymbol: response.top_model_drivers_by_symbol ?? {},
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
  const response = await fetchJson<ApiBenchmarkResponse>('/api/v1/benchmarks/summary');
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
  }));

  const projectedGrowth = response.projected_growth.map((row) => ({
    year: row.year,
    ...row.values,
  }));

  const winner = strategies.reduce((best, current) => (current.sharpe > best.sharpe ? current : best)).name;
  return { strategies, projectedGrowth, winner, notes: response.notes ?? [] };
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

function buildPortfolioContextPayload(portfolio: Portfolio | null) {
  if (!portfolio) return {};
  return {
    total_invested: portfolio.totalInvested,
    risk_profile: portfolio.riskProfile,
    mandate: portfolio.mandate ?? null,
    metrics: {
      avg_beta: portfolio.metrics.avgBeta,
      estimated_annual_return: portfolio.metrics.estimatedAnnualReturn,
      estimated_volatility: portfolio.metrics.estimatedVolatility,
      sharpe_ratio: portfolio.metrics.sharpeRatio,
      diversification_score: portfolio.metrics.correlationScore,
    },
    allocations: portfolio.allocations.map((allocation) => ({
      symbol: allocation.stock.symbol,
      sector: allocation.stock.sector,
      weight: allocation.weight,
      drivers: allocation.drivers ?? [],
      rationale: allocation.rationale ?? '',
      ml_pred_21d_return: allocation.ml_pred_21d_return ?? null,
      ml_pred_annual_return: allocation.ml_pred_annual_return ?? null,
      death_risk: allocation.death_risk ?? null,
      lstm_signal: allocation.lstm_signal ?? null,
      news_sentiment: allocation.news_sentiment ?? null,
      news_impact: allocation.news_impact ?? null,
    })),
  };
}

function buildBacktestContextPayload(backtest: BacktestResult | null) {
  if (!backtest) return {};
  return {
    total_return: backtest.totalReturn,
    cagr: backtest.cagr,
    max_drawdown: backtest.maxDrawdown,
    sharpe: backtest.sharpe,
    sortino: backtest.sortino,
    calmar: backtest.calmar,
    win_rate: backtest.winRate,
    total_trades: backtest.totalTrades,
    final_value: backtest.finalValue,
    initial_investment: backtest.initialInvestment,
    model_variant: backtest.modelVariant ?? null,
    model_source: backtest.modelSource ?? null,
    notes: backtest.notes ?? [],
  };
}

export async function postExplainChat(
  message: string,
  history: ExplainChatHistoryItem[],
  groundedContext: Record<string, unknown>,
): Promise<CopilotChatResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/explain/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, history, grounded_context: groundedContext }),
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`API ${response.status}: ${body}`);
  }
  return response.json() as Promise<CopilotChatResponse>;
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

export async function postExplainTradeIdea(
  idea: TradeIdea,
  portfolio: Portfolio | null,
): Promise<{ explanation: string }> {
  const response = await fetch(`${API_BASE_URL}/api/v1/explain/trade-idea`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      idea,
      portfolio_context: buildPortfolioContextPayload(portfolio),
    }),
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`API ${response.status}: ${body}`);
  }
  return response.json() as Promise<{ explanation: string }>;
}

export async function postExplainBacktest(
  backtest: BacktestResult,
  portfolio: Portfolio | null,
): Promise<{ explanation: string }> {
  const response = await fetch(`${API_BASE_URL}/api/v1/explain/backtest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      result: buildBacktestContextPayload(backtest),
      portfolio_context: buildPortfolioContextPayload(portfolio),
    }),
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`API ${response.status}: ${body}`);
  }
  return response.json() as Promise<{ explanation: string }>;
}
