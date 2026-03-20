import { LIQUID_ASSETS, NSE_STOCKS } from '../data/stocks';
import { ComparisonResult, BenchmarkStrategy } from './benchmarkService';
import { BacktestConfig, BacktestResult } from './backtestEngine';
import {
  AnalysisResult,
  Portfolio,
  RiskProfile,
} from './portfolioService';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const ALL_STOCKS = [...NSE_STOCKS, ...LIQUID_ASSETS];

type ApiRiskMode = 'ULTRA_LOW' | 'MODERATE' | 'HIGH';

interface ApiGeneratePortfolioResponse {
  risk_mode: ApiRiskMode;
  investment_amount: number;
  allocations: { symbol: string; sector: string; weight: number; rationale: string }[];
  metrics: {
    estimated_return_pct: number;
    estimated_volatility_pct: number;
    beta: number;
    diversification_score: number;
  };
}

interface ApiAnalyzePortfolioResponse {
  portfolio_value: number;
  current_beta: number;
  diversification_score: number;
  sector_weights: Record<string, number>;
  correlation_risk: 'LOW' | 'MODERATE' | 'HIGH';
  actions: { symbol: string; action: 'BUY' | 'SELL' | 'HOLD'; target_weight: number; current_weight: number; reason: string }[];
  notes: string[];
}

interface ApiBacktestResponse {
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
    total_tax: number;
  };
  cost_breakdown: {
    total_brokerage: number;
    total_stt: number;
    total_stamp_duty: number;
    total_gst: number;
    total_slippage: number;
    total_costs: number;
  };
  equity_curve: { date: string; portfolio_value: number; benchmark_value: number }[];
}

interface ApiBenchmarkResponse {
  strategies: {
    name: string;
    description: string;
    category: 'AI' | 'INDEX' | 'FACTOR' | 'AMC_STYLE';
    annual_return_pct: number;
    volatility_pct: number;
    sharpe_ratio: number;
    sortino_ratio: number;
    max_drawdown_pct: number;
    cagr_5y_pct: number;
    expense_ratio_pct: number;
  }[];
  projected_growth: { year: number; values: Record<string, number> }[];
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

export async function generatePortfolioViaApi(amount: number, risk: RiskProfile): Promise<Portfolio> {
  const response = await fetchJson<ApiGeneratePortfolioResponse>('/api/v1/portfolio/generate', {
    method: 'POST',
    body: JSON.stringify({
      investment_amount: amount,
      risk_mode: toApiRiskMode(risk),
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
      };
    })
    .filter(Boolean) as Portfolio['allocations'];

  const totalInvested = allocations.reduce((sum, allocation) => sum + allocation.amount, 0);
  const sectorCount = new Set(allocations.map((allocation) => allocation.stock.sector)).size;

  return {
    allocations,
    totalInvested,
    riskProfile: fromApiRiskMode(response.risk_mode),
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
    correlationWarnings:
      response.correlation_risk === 'HIGH'
        ? ['High empirical correlation risk detected by the backend analyzer.']
        : response.correlation_risk === 'MODERATE'
          ? ['Moderate cross-sector correlation risk detected.']
          : [],
    totalValue: response.portfolio_value,
  };
}

export async function runBacktestViaApi(
  portfolio: Portfolio,
  config: BacktestConfig,
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
      totalTax: response.tax_liability.total_tax,
    },
    costBreakdown: {
      totalBrokerage: response.cost_breakdown.total_brokerage,
      totalSTT: response.cost_breakdown.total_stt,
      totalStampDuty: response.cost_breakdown.total_stamp_duty,
      totalGST: response.cost_breakdown.total_gst,
      totalSlippage: response.cost_breakdown.total_slippage,
      totalCosts: response.cost_breakdown.total_costs,
    },
    config,
    initialInvestment: response.metrics.initial_investment,
  };
}

export async function getBenchmarkComparisonViaApi(): Promise<ComparisonResult> {
  const response = await fetchJson<ApiBenchmarkResponse>('/api/v1/benchmarks/summary');
  const strategies: BenchmarkStrategy[] = response.strategies.map((strategy) => ({
    name: strategy.name,
    description: strategy.description,
    annualReturn: strategy.annual_return_pct,
    volatility: strategy.volatility_pct,
    maxDrawdown: strategy.max_drawdown_pct,
    sharpe: strategy.sharpe_ratio,
    sortino: strategy.sortino_ratio,
    cagr5Y: strategy.cagr_5y_pct,
    expenseRatio: strategy.expense_ratio_pct,
    type: strategy.category === 'AI' ? 'AI' : strategy.category === 'INDEX' ? 'INDEX' : 'QUANT',
  }));

  const projectedGrowth = response.projected_growth.map((row) => ({
    year: row.year,
    ...row.values,
  }));

  const winner = strategies.reduce((best, current) => (current.sharpe > best.sharpe ? current : best)).name;
  return { strategies, projectedGrowth, winner };
}
