import type { Portfolio } from './portfolioService';

export interface RuntimeDescriptor {
  variant: 'RULES' | 'LIGHTGBM_HYBRID';
  modelSource: 'RULES' | 'ENSEMBLE';
  activeMode: string;
  modelVersion: string;
  artifactClassification: string;
  predictionHorizonDays: number;
}

export interface StandardMetrics {
  returnPct: number;
  volatilityPct: number;
  sharpeRatio: number;
  diversificationScore?: number;
  correlation?: number;
  beta?: number;
}

export interface RiskContribution {
  name: string;
  weightPct: number;
  contributionPct: number;
  detail: string;
}

export interface PortfolioConstraintStatus {
  maxPositionCapPct: number;
  maxSectorCapPct: number;
  largestPositionPct: number;
  largestPositionName: string;
  largestSectorWeightPct: number;
  largestSectorName: string;
  nearPositionCap: boolean;
  nearSectorCap: boolean;
}

export interface ScenarioShock {
  name: string;
  pnlPct: number;
  commentary: string;
}

export interface BenchmarkRelativeStats {
  benchmarkName: string;
  activeSharePct: number;
  trackingErrorPct: number;
  exAnteAlphaPct: number;
  informationRatio: number;
}

export interface PortfolioFitSummary {
  summary: string;
  riskLevel: string;
  diversification: string;
  concentration: string;
  nextAction: string;
}

export interface MarketTrendBlock {
  indexSymbol: string;
  spot: number;
  dma50: number;
  dma200: number;
  above50Dma: boolean;
  above200Dma: boolean;
  breadthAbove50Pct: number;
  breadthAbove200Pct: number;
  realizedVolatilityPct: number;
  drawdownPct: number;
  drawdownState: string;
}

export interface MarketFactorWeatherItem {
  factor: string;
  leadershipScore: number;
  leader: string;
  note: string;
  dataQuality: 'live' | 'proxy' | 'placeholder';
}

export interface CrossAssetToneItem {
  asset: string;
  tone: string;
  movePct: number;
  note: string;
  dataQuality: 'live' | 'proxy' | 'placeholder';
}

export interface SectorRelativeStrength {
  sector: string;
  return1mPct: number;
  return3mPct: number;
  return6mPct: number;
  earningsRevisionTrend: string;
  note: string;
}

export function defaultRuntimeDescriptor(): RuntimeDescriptor {
  return {
    variant: 'RULES',
    modelSource: 'RULES',
    activeMode: 'rules_only',
    modelVersion: 'rules',
    artifactClassification: 'missing',
    predictionHorizonDays: 21,
  };
}

export function inferPortfolioFitFromPortfolio(portfolio: Portfolio | null): PortfolioFitSummary | null {
  if (!portfolio) return null;
  const largestAllocation = [...portfolio.allocations].sort((left, right) => right.weight - left.weight)[0];
  const sectorTotals = portfolio.allocations.reduce<Record<string, number>>((acc, allocation) => {
    acc[allocation.stock.sector] = (acc[allocation.stock.sector] || 0) + allocation.weight;
    return acc;
  }, {});
  const [largestSectorName, largestSectorWeight] =
    Object.entries(sectorTotals).sort((left, right) => right[1] - left[1])[0] || ['N/A', 0];
  const riskLevel =
    portfolio.metrics.avgBeta >= 1.15 || portfolio.metrics.estimatedVolatility >= 20
      ? 'high'
      : portfolio.metrics.avgBeta >= 0.9
        ? 'balanced'
        : 'defensive';
  const diversification =
    portfolio.metrics.correlationScore >= 75 ? 'strong' : portfolio.metrics.correlationScore >= 55 ? 'moderate' : 'narrow';
  const concentration = largestAllocation
    ? `${largestAllocation.stock.symbol} ${largestAllocation.weight.toFixed(1)}%, ${largestSectorName} ${largestSectorWeight.toFixed(1)}%`
    : 'no active concentration';
  const nextAction =
    (portfolio.cashRemaining || 0) > 0
      ? `Deploy residual cash of Rs ${(portfolio.cashRemaining || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })} gradually.`
      : 'Monitor concentration and refresh if market breadth weakens.';
  return {
    summary: `Risk level: ${riskLevel}. Diversification: ${diversification}. Concentration: ${concentration}. Next action: ${nextAction}`,
    riskLevel,
    diversification,
    concentration,
    nextAction,
  };
}

export function formatPortfolioFitLine(summary: PortfolioFitSummary | null | undefined): string {
  if (!summary) return 'Risk level, diversification, and next action will appear here once the portfolio context is loaded.';
  return summary.summary;
}
