export interface BacktestConfig {
  startDate: string;
  endDate: string;
  stopLossPct: number;
  takeProfitPct: number;
  rebalanceFreq: 'Monthly' | 'Quarterly' | 'Annually' | 'None';
  slippagePct: number;
}

export interface BacktestResult {
  equityCurve: { date: string; value: number; benchmark: number }[];
  finalValue: number;
  totalReturn: number;
  cagr: number;
  maxDrawdown: number;
  sharpe: number;
  sortino: number;
  calmar: number;
  winRate: number;
  turnoverPct?: number;
  totalTrades: number;
  taxLiability: TaxBreakdown;
  costBreakdown: CostBreakdown;
  config: BacktestConfig;
  initialInvestment: number;
  notes?: string[];
  modelVariant?: 'RULES' | 'LIGHTGBM_HYBRID';
  modelSource?: 'RULES' | 'LIGHTGBM' | 'ENSEMBLE';
  modelVersion?: string;
  predictionHorizonDays?: number;
  activeMode?: string;
  artifactClassification?: string;
  topModelDriversBySymbol?: { [key: string]: string[] };
  validationAsOfDate?: string;
  validationHorizonDays?: number;
  validationSamples?: number;
  validationHitRatePct?: number;
  validationMaePct?: number;
  predictionValidation?: {
    symbol: string;
    predictedReturnPct: number;
    actualReturnPct: number;
    absoluteErrorPct: number;
    directionMatch: boolean;
  }[];
}

export interface TaxBreakdown {
  stcgGain: number;
  ltcgGain: number;
  stcgTax: number;
  ltcgTax: number;
  cessTax: number;
  totalTax: number;
}

export interface CostBreakdown {
  totalBrokerage: number;
  totalSTT: number;
  totalStampDuty: number;
  totalExchangeTxn: number;
  totalSebiFees: number;
  totalGST: number;
  totalSlippage: number;
  totalCosts: number;
}
