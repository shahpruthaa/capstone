import { NSE_STOCKS, LIQUID_ASSETS, SECTOR_CORRELATIONS } from '../data/stocks';
import { AnalysisResult, Portfolio, RiskProfile } from './portfolioService';

type Holding = { symbol: string; shares: number };

const ALL_STOCKS = [...NSE_STOCKS, ...LIQUID_ASSETS];

function formatCurrency(amount: number): string {
  return `Rs ${Math.round(amount).toLocaleString('en-IN')}`;
}

function riskLabel(risk: RiskProfile): string {
  if (risk === 'NO_RISK') return 'ultra-low risk';
  if (risk === 'LOW_RISK') return 'moderate risk';
  return 'high risk';
}

function getTopAllocations(portfolio: Portfolio, count = 3): string {
  return [...portfolio.allocations]
    .sort((a, b) => b.weight - a.weight)
    .slice(0, count)
    .map((allocation) => `${allocation.stock.symbol} (${allocation.weight}%)`)
    .join(', ');
}

function getSectorExposureFromPortfolio(portfolio: Portfolio): Array<[string, number]> {
  const sectorMap = new Map<string, number>();

  portfolio.allocations.forEach((allocation) => {
    sectorMap.set(
      allocation.stock.sector,
      (sectorMap.get(allocation.stock.sector) ?? 0) + allocation.weight,
    );
  });

  return [...sectorMap.entries()].sort((a, b) => b[1] - a[1]);
}

function getCorrelationNote(portfolio: Portfolio): string {
  const sectors = getSectorExposureFromPortfolio(portfolio).map(([sector]) => sector);
  if (sectors.length < 2) return 'Sector breadth is still limited, so diversification is fragile.';

  let totalCorrelation = 0;
  let pairs = 0;

  for (let i = 0; i < sectors.length; i++) {
    for (let j = i + 1; j < sectors.length; j++) {
      totalCorrelation += SECTOR_CORRELATIONS[sectors[i]]?.[sectors[j]] ?? 0.5;
      pairs++;
    }
  }

  const averageCorrelation = pairs === 0 ? 0.5 : totalCorrelation / pairs;

  if (averageCorrelation <= 0.3) {
    return 'Cross-sector correlation is relatively low, which should help cushion drawdowns.';
  }
  if (averageCorrelation <= 0.55) {
    return 'Diversification is reasonable, but cyclical sectors could still move together in a stress regime.';
  }
  return 'Average correlation is elevated, so the portfolio may behave more like a concentrated beta trade than a diversified basket.';
}

export function generatePortfolioInsight(portfolio: Portfolio): string {
  const topSector = getSectorExposureFromPortfolio(portfolio)[0];
  const hedgePresent = portfolio.allocations.some((allocation) =>
    ['Gold', 'Liquid', 'Silver'].includes(allocation.stock.sector),
  );

  const summary = `This ${riskLabel(portfolio.riskProfile)} portfolio deploys ${formatCurrency(portfolio.totalInvested)} across ${portfolio.metrics.sectorCount} sectors, led by ${topSector?.[0] ?? 'diversified'} exposure.`;
  const composition = `The main weights are ${getTopAllocations(portfolio)}, with portfolio beta at ${portfolio.metrics.avgBeta.toFixed(2)} and an estimated return/volatility profile of ${portfolio.metrics.estimatedAnnualReturn.toFixed(1)}% / ${portfolio.metrics.estimatedVolatility.toFixed(1)}%.`;
  const hedgeComment = hedgePresent
    ? 'It already includes defensive ballast through hedge-like assets, which is useful for Indian risk-off phases.'
    : 'It lacks an explicit hedge sleeve, so adding gold or liquid funds would improve resilience during market shocks.';

  return `${summary} ${composition} ${getCorrelationNote(portfolio)} ${hedgeComment}`;
}

export function generateRebalancingAdvice(
  holdings: Holding[],
  result: AnalysisResult,
): string {
  const bullets: string[] = [];
  const totalSectors = Object.keys(result.sectorWeights).length;

  if (result.riskScore > 1.3) {
    bullets.push('Reduce high-beta names and shift part of the portfolio toward FMCG, Pharma, or Bharat-focused large caps.');
  } else if (result.riskScore < 0.8) {
    bullets.push('Risk is conservative; if the goal is balanced growth, gradually add quality cyclicals or broad-market ETFs.');
  }

  if (result.diversificationScore < 45 || totalSectors < 4) {
    bullets.push('Increase sector breadth to at least 5 to 6 sleeves so performance is not dominated by one market regime.');
  }

  const sectorEntries = Object.entries(result.sectorWeights).sort((a, b) => b[1] - a[1]);
  const topSector = sectorEntries[0];
  if (topSector && topSector[1] > 35) {
    bullets.push(`Trim the heaviest sector, currently ${topSector[0]} at ${topSector[1].toFixed(1)}%, and recycle capital into lower-correlation sectors.`);
  }

  if (!sectorEntries.some(([sector]) => sector === 'Gold' || sector === 'Liquid')) {
    bullets.push('Add a hedge sleeve such as Gold ETF or Liquid ETF to improve downside protection and rebalance flexibility.');
  }

  if (holdings.length > 0 && result.rebalancingActions.length > 0) {
    const names = result.rebalancingActions
      .slice(0, 3)
      .map((action) => action.symbol)
      .join(', ');
    bullets.push(`Priority review names: ${names}. These positions look most out of line with the current diversification target.`);
  }

  return bullets.slice(0, 4).map((bullet) => `- ${bullet}`).join('\n');
}

function portfolioSummaryForChat(portfolio: Portfolio | null): string {
  if (!portfolio) {
    return 'No live portfolio is loaded, so I would start from risk mode selection and sector diversification.';
  }

  const sectorLead = getSectorExposureFromPortfolio(portfolio)[0];
  return `Your current portfolio is ${riskLabel(portfolio.riskProfile)} with beta ${portfolio.metrics.avgBeta.toFixed(2)} and the largest sector weight in ${sectorLead?.[0] ?? 'diversified holdings'}.`;
}

function answerTaxQuestion(): string {
  return 'For the current simulation, delivery equity taxes use STCG at 20%, LTCG at 12.5% after the Rs 1.25 lakh annual exemption, plus STT, stamp duty, brokerage, GST, and slippage. In production, these should be versioned by transaction date so tax treatment stays historically accurate.';
}

function answerRiskQuestion(portfolio: Portfolio | null): string {
  if (!portfolio) {
    return 'The three risk modes should map to distinct universes and constraints: ultra-low risk for liquid, gold, and defensive large caps; balanced for diversified quality growth; and high risk for smaller, higher-beta, momentum-heavy names. The right mode depends more on drawdown tolerance and holding period than on return targets alone.';
  }

  return `${portfolioSummaryForChat(portfolio)} If you want lower drawdowns, reduce sectors with high cyclicality and increase allocations to low-beta defensives or hedge assets.`;
}

function answerDiversificationQuestion(portfolio: Portfolio | null): string {
  if (!portfolio) {
    return 'For NSE portfolios, diversification should be measured across sectors, factors, market-cap buckets, and hedge sleeves rather than stock count alone. A concentrated set of highly correlated large caps can still behave like one trade.';
  }

  return `${portfolioSummaryForChat(portfolio)} The current diversification score is ${portfolio.metrics.correlationScore.toFixed(0)}, so the next step is to compare top sector concentration with pairwise correlation and reduce overlap where needed.`;
}

function answerBacktestQuestion(): string {
  return 'A credible Indian backtest needs corporate actions, realistic fill logic, stop-loss and take-profit triggers, slippage by liquidity bucket, and dated tax rules for STT, STCG, LTCG, and stamp duty. The current repo has the shell of that engine, but it still uses simulated GBM paths instead of exchange-grade historical bars.';
}

function answerBenchmarkQuestion(): string {
  return 'Benchmarking should include Nifty 50, Nifty 500, equal-weight, minimum-variance, momentum, quality, and AMC-style factor sleeves. The important comparison is not raw CAGR alone, but excess return after turnover, taxes, drawdown, and tracking error.';
}

function answerGenerationQuestion(portfolio: Portfolio | null): string {
  if (!portfolio) {
    return 'Start with a constrained optimizer: define the eligible NSE universe, cap sector and single-name weights, penalize correlation, and target a volatility band for each risk mode. That gives you a portfolio generator that is explainable and easier to govern than a purely black-box model.';
  }

  return `${portfolioSummaryForChat(portfolio)} A stronger next version would replace static weights with factor scores, correlation-aware optimization, and regime-sensitive rebalancing rules.`;
}

function genericAnswer(portfolio: Portfolio | null): string {
  return `${portfolioSummaryForChat(portfolio)} This local assistant is deterministic, so it focuses on portfolio construction, diversification, taxes, backtesting, and NSE-specific workflow guidance rather than external market news.`;
}

export function answerChatQuestion(question: string, portfolio: Portfolio | null): string {
  const normalized = question.toLowerCase();

  if (normalized.includes('tax') || normalized.includes('stcg') || normalized.includes('ltcg') || normalized.includes('stt')) {
    return answerTaxQuestion();
  }

  if (normalized.includes('risk') || normalized.includes('beta') || normalized.includes('volatile') || normalized.includes('drawdown')) {
    return answerRiskQuestion(portfolio);
  }

  if (normalized.includes('divers') || normalized.includes('correlation') || normalized.includes('sector')) {
    return answerDiversificationQuestion(portfolio);
  }

  if (normalized.includes('backtest') || normalized.includes('simulation') || normalized.includes('stop-loss') || normalized.includes('take-profit')) {
    return answerBacktestQuestion();
  }

  if (normalized.includes('benchmark') || normalized.includes('nifty') || normalized.includes('amc') || normalized.includes('factor')) {
    return answerBenchmarkQuestion();
  }

  if (normalized.includes('generate') || normalized.includes('build') || normalized.includes('buy') || normalized.includes('portfolio')) {
    return answerGenerationQuestion(portfolio);
  }

  return genericAnswer(portfolio);
}

export function lookupHoldingLabel(symbol: string): string {
  return ALL_STOCKS.find((stock) => stock.symbol === symbol)?.name ?? symbol;
}
