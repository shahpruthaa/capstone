import { NSE_STOCKS, LIQUID_ASSETS, SECTOR_CORRELATIONS, Stock } from '../data/stocks';

export type RiskProfile = 'NO_RISK' | 'LOW_RISK' | 'HIGH_RISK';

export interface Allocation {
  stock: Stock;
  weight: number;   // percentage 0-100
  shares: number;
  amount: number;
  drivers?: string[];
  rationale?: string;
  ml_pred_21d_return?: number | null;
  ml_pred_annual_return?: number | null;
  death_risk?: number | null;
  lstm_signal?: number | null;
  news_risk_score?: number;
  news_opportunity_score?: number;
  news_sentiment?: number;
  news_impact?: number;
  news_explanation?: string;
}

export interface Portfolio {
  allocations: Allocation[];
  totalInvested: number;
  requestedCapital?: number;
  cashRemaining?: number;
  investmentUtilizationPct?: number;
  riskProfile: RiskProfile;
  mandate?: {
    investment_horizon_weeks: string;
    preferred_num_positions: number;
    allow_small_caps: boolean;
    risk_attitude: string;
  };
  metrics: PortfolioMetrics;
  backendNotes?: string[];
  modelVariant?: 'RULES' | 'LIGHTGBM_HYBRID';
  modelSource?: 'RULES' | 'ENSEMBLE';
  modelVersion?: string;
  predictionHorizonDays?: number;
  lookbackWindowDays?: number;
  expectedHoldingPeriodDays?: number;
  regimeWarning?: string;
  runtime?: {
    variant: 'RULES' | 'LIGHTGBM_HYBRID';
    modelSource: 'RULES' | 'ENSEMBLE';
    activeMode: string;
    modelVersion: string;
    artifactClassification: string;
    predictionHorizonDays: number;
  };
  standardMetrics?: {
    returnPct: number;
    volatilityPct: number;
    sharpeRatio: number;
    diversificationScore?: number;
    correlation?: number;
    beta?: number;
  };
  factorExposures?: { [key: string]: number };
  positionRiskContributions?: Array<{ name: string; weightPct: number; contributionPct: number; detail: string }>;
  sectorRiskContributions?: Array<{ name: string; weightPct: number; contributionPct: number; detail: string }>;
  constraints?: {
    maxPositionCapPct: number;
    maxSectorCapPct: number;
    largestPositionPct: number;
    largestPositionName: string;
    largestSectorWeightPct: number;
    largestSectorName: string;
    nearPositionCap: boolean;
    nearSectorCap: boolean;
  };
  turnoverEstimatePct?: number;
  deploymentEfficiencyPct?: number;
  scenarioTests?: Array<{ name: string; pnlPct: number; commentary: string }>;
  benchmarkRelative?: {
    benchmarkName: string;
    activeSharePct: number;
    trackingErrorPct: number;
    exAnteAlphaPct: number;
    informationRatio: number;
  };
  portfolioFitSummary?: {
    summary: string;
    riskLevel: string;
    diversification: string;
    concentration: string;
    nextAction: string;
  };
}

export interface PortfolioMetrics {
  avgBeta: number;
  estimatedAnnualReturn: number; // % pa
  estimatedVolatility: number;   // % pa
  sharpeRatio: number;
  divScore: number;              // 0-100
  correlationScore: number;      // 0-100, higher = better diversified
  sectorCount: number;
}

export interface AnalysisResult {
  riskScore: number;
  diversificationScore: number;
  suggestions: string[];
  rebalancingActions: RebalancingAction[];
  sectorWeights: { [key: string]: number };
  factorExposures?: { [key: string]: number };
  correlationWarnings: string[];
  totalValue: number;
  totalHoldings?: number;
  avgPairwiseCorrelation?: number;
  largestSector?: string;
  largestSectorWeight?: number;
  healthLabel?: 'GOOD' | 'OKAY' | 'CAUTION';
  healthSummary?: string;
  riskAssessment?: string;
  diversificationAssessment?: string;
  concentrationAssessment?: string;
  factorAssessment?: string;
  correlationAssessment?: string;
  benchmarkAssessment?: string;
  idiosyncraticRiskAssessment?: string;
  rebalanceSummary?: string;
  portfolioFitSummary?: {
    summary: string;
    riskLevel: string;
    diversification: string;
    concentration: string;
    nextAction: string;
  };
  standardMetrics?: {
    returnPct: number;
    volatilityPct: number;
    sharpeRatio: number;
    diversificationScore?: number;
    correlation?: number;
    beta?: number;
  };
  runtime?: {
    variant: 'RULES' | 'LIGHTGBM_HYBRID';
    modelSource: 'RULES' | 'ENSEMBLE';
    activeMode: string;
    modelVersion: string;
    artifactClassification: string;
    predictionHorizonDays: number;
  };
  recommendedActions?: string[];
  backendNotes?: string[];
  modelVariantApplied?: 'RULES' | 'LIGHTGBM_HYBRID';
  modelSource?: 'RULES' | 'ENSEMBLE';
  activeMode?: string;
  modelVersion?: string;
  artifactClassification?: string;
  holdingPeriodDaysRecommended?: number;
  predictionHorizonDays?: number;
  holdingPeriodReason?: string;
  mlPredictions?: { [key: string]: number };
  topModelDriversBySymbol?: { [key: string]: string[] };
}

export interface RebalancingAction {
  symbol: string;
  action: 'BUY' | 'SELL' | 'HOLD';
  reason: string;
  targetWeight: number;
  currentWeight: number;
}

// ─── Indian Market Cost Constants ────────────────────────────────────────────
export const BROKERAGE_RATE = 0.0003;    // 0.03% per order
export const MAX_BROKERAGE = 20;        // ₹20 cap per order
export const STT_BUY_RATE = 0.001;     // 0.1% on buy
export const STT_SELL_RATE = 0.001;     // 0.1% on sell delivery
export const STAMP_DUTY_RATE = 0.00015;   // 0.015% on buy only
export const EXCHANGE_TXN_RATE = 0.000030699; // current NSE CM charge approx. 2026-03-01 onwards
export const GST_RATE = 0.18;      // 18% on brokerage + exchange + sebi
export const SEBI_CHARGES = 0.000001;  // ₹1 per ₹1 crore
export const SLIPPAGE_RATE = 0.001;     // 0.1% assumed slippage

// ─── Tax Constants ────────────────────────────────────────────────────────────
export const STCG_RATE = 0.20;      // 20% Short-Term Capital Gains (budget 2024)
export const LTCG_RATE = 0.125;     // 12.5% Long-Term Capital Gains
export const LTCG_EXEMPTION = 125000;    // ₹1.25L exemption pa (budget 2024)

// ─── Transaction Cost Calculation ────────────────────────────────────────────
export function calculateTransactionCosts(amount: number, isBuy: boolean = true): {
  brokerage: number; stt: number; stampDuty: number; exchangeTxn: number; gst: number; sebi: number; slippage: number; total: number;
} {
  const brokerage = Math.min(amount * BROKERAGE_RATE, MAX_BROKERAGE);
  const stt = amount * (isBuy ? STT_BUY_RATE : STT_SELL_RATE);
  const stampDuty = isBuy ? amount * STAMP_DUTY_RATE : 0;
  const exchangeTxn = amount * EXCHANGE_TXN_RATE;
  const sebi = amount * SEBI_CHARGES;
  const gst = (brokerage + exchangeTxn + sebi) * GST_RATE;
  const slippage = amount * SLIPPAGE_RATE;
  const total = brokerage + stt + stampDuty + exchangeTxn + gst + sebi + slippage;
  return { brokerage, stt, stampDuty, exchangeTxn, gst, sebi, slippage, total };
}

export function calculatePortfolioTransactionCosts(
  allocations: Array<{ amount: number }>,
  isBuy: boolean = true,
): {
  brokerage: number; stt: number; stampDuty: number; exchangeTxn: number; gst: number; sebi: number; slippage: number; total: number;
} {
  return allocations.reduce(
    (totals, allocation) => {
      const costs = calculateTransactionCosts(allocation.amount, isBuy);
      totals.brokerage += costs.brokerage;
      totals.stt += costs.stt;
      totals.stampDuty += costs.stampDuty;
      totals.exchangeTxn += costs.exchangeTxn;
      totals.gst += costs.gst;
      totals.sebi += costs.sebi;
      totals.slippage += costs.slippage;
      totals.total += costs.total;
      return totals;
    },
    { brokerage: 0, stt: 0, stampDuty: 0, exchangeTxn: 0, gst: 0, sebi: 0, slippage: 0, total: 0 },
  );
}

// ─── Portfolio Sector Correlation Score ──────────────────────────────────────
function computeCorrelationScore(stocks: Stock[]): number {
  if (stocks.length < 2) return 0;
  let totalCorr = 0;
  let pairs = 0;
  const sectors = stocks.map(s => s.sector);
  for (let i = 0; i < sectors.length; i++) {
    for (let j = i + 1; j < sectors.length; j++) {
      const corr = (SECTOR_CORRELATIONS[sectors[i]]?.[sectors[j]]) ?? 0.5;
      totalCorr += corr;
      pairs++;
    }
  }
  const avgCorr = pairs > 0 ? totalCorr / pairs : 0.5;
  // Convert avg correlation to score: 0 corr → 100, 1.0 corr → 0
  return Math.max(0, Math.min(100, (1 - avgCorr) * 100));
}

// ─── Portfolio Metrics Computation ───────────────────────────────────────────
function computeMetrics(stocks: Stock[], weights: number[], riskProfile: RiskProfile): PortfolioMetrics {
  const riskFreeRate = 7.0; // ~7% (Indian 10yr g-sec yield)

  let avgBeta = 0;
  const sectors = new Set<string>();

  stocks.forEach((s, i) => {
    avgBeta += s.beta * (weights[i] / 100);
    sectors.add(s.sector);
  });

  // Estimate annualised return based on risk profile and beta
  const baseReturn = riskProfile === 'NO_RISK' ? 7.5 : riskProfile === 'LOW_RISK' ? 12.0 : 18.0;
  const betaAdj = (avgBeta - 1) * 5;
  const estimatedAnnualReturn = Math.max(5, baseReturn + betaAdj);

  // Estimated volatility: Large cap ~15%, Mid ~25%, Small ~35%
  const baseVol = riskProfile === 'NO_RISK' ? 4.0 : riskProfile === 'LOW_RISK' ? 14.0 : 28.0;
  const estimatedVolatility = baseVol * avgBeta;

  const sharpeRatio = (estimatedAnnualReturn - riskFreeRate) / Math.max(estimatedVolatility, 1);
  const divScore = Math.min(100, sectors.size * 10 + (stocks.length > 8 ? 20 : 0));
  const correlationScore = computeCorrelationScore(stocks);

  return { avgBeta, estimatedAnnualReturn, estimatedVolatility, sharpeRatio, divScore, correlationScore, sectorCount: sectors.size };
}

// ─── Portfolio Generator ──────────────────────────────────────────────────────
export function generatePortfolio(amount: number, risk: RiskProfile): Portfolio {
  let selectedStocks: Stock[] = [];
  let weights: number[] = [];

  const ALL = [...NSE_STOCKS, ...LIQUID_ASSETS];

  if (risk === 'NO_RISK') {
    // Capital preservation: 60% Liquid + 25% Gold + 10% Silver + 5% Nifty ETF
    const liquid = LIQUID_ASSETS.find(s => s.symbol === 'LIQUIDBEES')!;
    const gold = LIQUID_ASSETS.find(s => s.symbol === 'GOLDBEES')!;
    const silver = LIQUID_ASSETS.find(s => s.symbol === 'SILVERBEES')!;
    const niftyEtf = LIQUID_ASSETS.find(s => s.symbol === 'NIFTYBEES')!;
    const hul = NSE_STOCKS.find(s => s.symbol === 'HINDUNILVR')!;
    const itc = NSE_STOCKS.find(s => s.symbol === 'ITC')!;
    const airtel = NSE_STOCKS.find(s => s.symbol === 'BHARTIARTL')!;
    const powergrid = NSE_STOCKS.find(s => s.symbol === 'POWERGRID')!;

    selectedStocks = [liquid, gold, silver, niftyEtf, hul, itc, airtel, powergrid];
    weights = [40, 20, 7, 8, 8, 7, 5, 5];

  } else if (risk === 'LOW_RISK') {
    // Diversified blue-chip: Defensive sectors, low beta, some growth
    const picks: { stock: Stock; weight: number }[] = [
      { stock: NSE_STOCKS.find(s => s.symbol === 'TCS')!, weight: 9 },
      { stock: NSE_STOCKS.find(s => s.symbol === 'INFY')!, weight: 8 },
      { stock: NSE_STOCKS.find(s => s.symbol === 'HDFCBANK')!, weight: 9 },
      { stock: NSE_STOCKS.find(s => s.symbol === 'HINDUNILVR')!, weight: 7 },
      { stock: NSE_STOCKS.find(s => s.symbol === 'ITC')!, weight: 6 },
      { stock: NSE_STOCKS.find(s => s.symbol === 'SUNPHARMA')!, weight: 7 },
      { stock: NSE_STOCKS.find(s => s.symbol === 'CIPLA')!, weight: 6 },
      { stock: NSE_STOCKS.find(s => s.symbol === 'BHARTIARTL')!, weight: 7 },
      { stock: NSE_STOCKS.find(s => s.symbol === 'POWERGRID')!, weight: 6 },
      { stock: NSE_STOCKS.find(s => s.symbol === 'RELIANCE')!, weight: 8 },
      { stock: LIQUID_ASSETS.find(s => s.symbol === 'GOLDBEES')!, weight: 10 },
      { stock: LIQUID_ASSETS.find(s => s.symbol === 'LIQUIDBEES')!, weight: 7 },
    ];
    selectedStocks = picks.map(p => p.stock);
    weights = picks.map(p => p.weight);

  } else {
    // HIGH_RISK: Growth-oriented, high beta, momentum, mid/small caps
    const picks: { stock: Stock; weight: number }[] = [
      { stock: NSE_STOCKS.find(s => s.symbol === 'ZOMATO')!, weight: 9 },
      { stock: NSE_STOCKS.find(s => s.symbol === 'ADANIGREEN')!, weight: 8 },
      { stock: NSE_STOCKS.find(s => s.symbol === 'TATAMOTORS')!, weight: 8 },
      { stock: NSE_STOCKS.find(s => s.symbol === 'KPITTECH')!, weight: 7 },
      { stock: NSE_STOCKS.find(s => s.symbol === 'COFORGE')!, weight: 7 },
      { stock: NSE_STOCKS.find(s => s.symbol === 'PERSISTENT')!, weight: 7 },
      { stock: NSE_STOCKS.find(s => s.symbol === 'DIVISLAB')!, weight: 6 },
      { stock: NSE_STOCKS.find(s => s.symbol === 'MUTHOOTFIN')!, weight: 6 },
      { stock: NSE_STOCKS.find(s => s.symbol === 'TATASTEEL')!, weight: 6 },
      { stock: NSE_STOCKS.find(s => s.symbol === 'DLF')!, weight: 6 },
      { stock: NSE_STOCKS.find(s => s.symbol === 'BHEL')!, weight: 5 },
      { stock: NSE_STOCKS.find(s => s.symbol === 'NYKAA')!, weight: 5 },
      { stock: LIQUID_ASSETS.find(s => s.symbol === 'GOLDBEES')!, weight: 5 },
      { stock: NSE_STOCKS.find(s => s.symbol === 'INDUSINDBK')!, weight: 5 },
    ];
    selectedStocks = picks.map(p => p.stock);
    weights = picks.map(p => p.weight);
  }

  // Filter out any undefined (safety guard)
  const validPicks = selectedStocks.map((stock, i) => ({ stock, weight: weights[i] })).filter(p => p.stock != null);
  selectedStocks = validPicks.map(p => p.stock);
  weights = validPicks.map(p => p.weight);

  const allocations: Allocation[] = selectedStocks.map((stock, i) => {
    const stockAmount = (amount * weights[i]) / 100;
    const shares = Math.max(1, Math.floor(stockAmount / stock.price));
    return { stock, weight: weights[i], shares, amount: shares * stock.price };
  });

  const totalInvested = allocations.reduce((acc, a) => acc + a.amount, 0);
  const metrics = computeMetrics(selectedStocks, weights, risk);

  return {
    allocations,
    totalInvested,
    riskProfile: risk,
    metrics,
    backendNotes: ['Local demo fallback only; metrics are heuristic and not live-market derived.'],
  };
}

// ─── Portfolio Analyzer ───────────────────────────────────────────────────────
export function analyzePortfolio(userPortfolio: { symbol: string; shares: number }[]): AnalysisResult {
  const ALL = [...NSE_STOCKS, ...LIQUID_ASSETS];
  let totalValue = 0;
  const sectorValue: { [key: string]: number } = {};
  let weightedBeta = 0;
  const stockValues: { symbol: string; value: number; sector: string; beta: number }[] = [];

  userPortfolio.forEach(item => {
    const stock = ALL.find(s => s.symbol === item.symbol);
    if (stock) {
      const value = stock.price * item.shares;
      totalValue += value;
      sectorValue[stock.sector] = (sectorValue[stock.sector] || 0) + value;
      weightedBeta += stock.beta * value;
      stockValues.push({ symbol: item.symbol, value, sector: stock.sector, beta: stock.beta });
    }
  });

  const avgBeta = totalValue > 0 ? weightedBeta / totalValue : 0;
  const sectorWeights: { [key: string]: number } = {};
  Object.keys(sectorValue).forEach(s => {
    sectorWeights[s] = (sectorValue[s] / totalValue) * 100;
  });

  const sectorList = Object.keys(sectorWeights);
  const correlationScore = computeCorrelationScore(
    stockValues.map(sv => ALL.find(s => s.symbol === sv.symbol)!)
      .filter(Boolean)
  );

  const suggestions: string[] = [];
  const correlationWarnings: string[] = [];
  const rebalancingActions: RebalancingAction[] = [];

  if (avgBeta > 1.4) suggestions.push('⚠️ Portfolio beta is very high. Consider adding FMCG or Pharma defensives.');
  if (sectorList.length < 4) suggestions.push('📊 You have fewer than 4 sectors. Diversify to reduce concentration risk.');
  if ((sectorWeights['Banking'] || 0) + (sectorWeights['Finance'] || 0) > 45)
    suggestions.push('🏦 Over-exposed to Banking+Finance (>45%). Reduce and diversify into IT or Pharma.');
  if ((sectorWeights['IT'] || 0) > 40) suggestions.push('💻 IT sector overweight (>40%). Balance with defensive sectors.');
  if (!sectorWeights['Gold'] && !sectorWeights['Liquid']) suggestions.push('🛡️ No hedge assets. Consider adding Gold ETF for downside protection.');
  if (correlationScore < 40) correlationWarnings.push('High inter-sector correlation detected. Stocks tend to move together.');

  // Rebalancing: suggest selling over-weighted sectors
  sectorList.forEach(sector => {
    const weight = sectorWeights[sector];
    const idealMaxWeight = sectorList.length > 1 ? 100 / sectorList.length + 10 : 100;
    if (weight > idealMaxWeight * 1.3) {
      const stocksInSector = stockValues.filter(sv => sv.sector === sector);
      stocksInSector.forEach(sv => {
        rebalancingActions.push({
          symbol: sv.symbol,
          action: 'SELL',
          reason: `${sector} sector overweight at ${weight.toFixed(1)}%`,
          targetWeight: idealMaxWeight,
          currentWeight: weight,
        });
      });
    }
  });

  return {
    riskScore: avgBeta,
    diversificationScore: Math.min(100, correlationScore),
    suggestions,
    rebalancingActions,
    sectorWeights,
    correlationWarnings,
    totalValue,
  };
}
