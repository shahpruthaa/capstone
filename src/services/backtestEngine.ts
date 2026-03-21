import { Portfolio, Allocation, calculateTransactionCosts, STCG_RATE, LTCG_RATE, LTCG_EXEMPTION } from './portfolioService';
import { NSE_STOCKS } from '../data/stocks';

export interface BacktestConfig {
    startDate: string;        // 'YYYY-MM-DD'
    endDate: string;
    stopLossPct: number;      // e.g. 0.15 = 15%
    takeProfitPct: number;    // e.g. 0.35 = 35%
    rebalanceFreq: 'Monthly' | 'Quarterly' | 'Annually' | 'None';
    slippagePct: number;      // e.g. 0.001 = 0.1%
}

export interface BacktestResult {
    equityCurve: { date: string; value: number; benchmark: number }[];
    finalValue: number;
    totalReturn: number;       // %
    cagr: number;              // %
    maxDrawdown: number;       // %
    sharpe: number;
    sortino: number;
    calmar: number;
    winRate: number;           // % of months positive
    totalTrades: number;
    taxLiability: TaxBreakdown;
    costBreakdown: CostBreakdown;
    config: BacktestConfig;
    initialInvestment: number;
    notes?: string[];
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

// ─── Geometric Brownian Motion price path generator ─────────────────────────
function generateGBMPath(
    startPrice: number,
    numDays: number,
    annualMu: number,     // expected annualised return (decimal)
    annualSigma: number,  // annualised volatility (decimal)
): number[] {
    const dt = 1 / 252;
    const prices: number[] = [startPrice];
    for (let i = 1; i < numDays; i++) {
        const u1 = Math.random();
        const u2 = Math.random();
        const z = Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2); // Box-Muller
        const drift = (annualMu - 0.5 * annualSigma ** 2) * dt;
        const diffusion = annualSigma * Math.sqrt(dt) * z;
        prices.push(prices[i - 1] * Math.exp(drift + diffusion));
    }
    return prices;
}

function getDaysBetween(start: string, end: string): number {
    const s = new Date(start).getTime();
    const e = new Date(end).getTime();
    return Math.round((e - s) / 86_400_000);
}

function addDays(dateStr: string, days: number): string {
    const d = new Date(dateStr);
    d.setDate(d.getDate() + days);
    return d.toISOString().slice(0, 10);
}

// Returns expected μ and σ based on risk profile and beta
function getStockParams(beta: number, riskProfile: string): { mu: number; sigma: number } {
    const baseReturn = riskProfile === 'NO_RISK' ? 0.075 : riskProfile === 'LOW_RISK' ? 0.12 : 0.18;
    const mu = baseReturn + (beta - 1) * 0.06;
    const sigma = 0.14 * beta + 0.04;
    return { mu, sigma };
}

// ─── Main backtest engine ─────────────────────────────────────────────────────
export function runBacktest(portfolio: Portfolio, config: BacktestConfig): BacktestResult {
    const { startDate, endDate, stopLossPct, takeProfitPct, rebalanceFreq } = config;
    const totalDays = Math.max(getDaysBetween(startDate, endDate), 2);
    const allDays = totalDays;
    const initialInvestment = portfolio.totalInvested;

    // Generate per-stock GBM price paths
    type StockState = {
        allocation: Allocation;
        prices: number[];
        buyPrice: number;
        active: boolean;
        buyDayIdx: number;
    };

    const states: StockState[] = portfolio.allocations.map(alloc => {
        const { mu, sigma } = getStockParams(alloc.stock.beta, portfolio.riskProfile);
        const prices = generateGBMPath(alloc.stock.price, allDays + 1, mu, sigma);
        return { allocation: alloc, prices, buyPrice: alloc.stock.price, active: true, buyDayIdx: 0 };
    });

    // Track costs and taxes
    const costs: CostBreakdown = {
        totalBrokerage: 0, totalSTT: 0, totalStampDuty: 0, totalExchangeTxn: 0, totalSebiFees: 0, totalGST: 0, totalSlippage: 0, totalCosts: 0
    };
    const taxes: TaxBreakdown = {
        stcgGain: 0, ltcgGain: 0, stcgTax: 0, ltcgTax: 0, cessTax: 0, totalTax: 0
    };

    let totalTrades = 0;
    const dailyReturns: number[] = [];
    const equityCurve: { date: string; value: number; benchmark: number }[] = [];

    // Benchmark: simple Nifty50 GBM (mu=12%, sigma=15%)
    const benchmarkPrices = generateGBMPath(100, allDays + 1, 0.12, 0.15);

    // Determine rebalance day interval
    const rebalanceInterval = rebalanceFreq === 'Monthly' ? 21 : rebalanceFreq === 'Quarterly' ? 63 : rebalanceFreq === 'Annually' ? 252 : Infinity;

    const cashReserve = { value: initialInvestment - portfolio.allocations.reduce((s, a) => s + a.amount, 0) };
    let prevPortfolioValue = initialInvestment;

    for (let day = 0; day <= allDays; day++) {
        const dateStr = addDays(startDate, day);
        let portfolioValue = cashReserve.value;

        states.forEach(state => {
            if (!state.active) return;
            const currentPrice = state.prices[day];
            const currentValue = currentPrice * state.allocation.shares;

            const returnPct = (currentPrice - state.buyPrice) / state.buyPrice;

            // Stop-loss trigger
            if (returnPct <= -stopLossPct) {
                const sellCost = calculateTransactionCosts(currentValue, false);
                costs.totalBrokerage += sellCost.brokerage;
                costs.totalSTT += sellCost.stt;
                costs.totalGST += sellCost.gst;
                costs.totalCosts += sellCost.total;
                const holdingDays = day - state.buyDayIdx;
                const gain = currentValue - state.allocation.amount;
                if (holdingDays < 365 && gain < 0) taxes.stcgGain += gain; // loss
                totalTrades++;
                cashReserve.value += currentValue - sellCost.total;
                state.active = false;
                return;
            }

            // Take-profit trigger
            if (returnPct >= takeProfitPct) {
                const sellCost = calculateTransactionCosts(currentValue, false);
                costs.totalBrokerage += sellCost.brokerage;
                costs.totalSTT += sellCost.stt;
                costs.totalGST += sellCost.gst;
                costs.totalCosts += sellCost.total;
                const holdingDays = day - state.buyDayIdx;
                const gain = currentValue - state.allocation.amount;
                if (holdingDays < 365) { taxes.stcgGain += gain; }
                else { taxes.ltcgGain += gain; }
                totalTrades++;
                cashReserve.value += currentValue - sellCost.total;
                state.active = false;
                return;
            }

            portfolioValue += currentValue;
        });

        portfolioValue += cashReserve.value;

        // Rebalancing: re-buy inactive positions at rebalance intervals
        if (rebalanceFreq !== 'None' && day > 0 && day % rebalanceInterval === 0) {
            const inactiveStates = states.filter(s => !s.active);
            inactiveStates.forEach(state => {
                if (cashReserve.value >= state.allocation.amount * 0.5) {
                    const buyAmount = Math.min(cashReserve.value * 0.9 / inactiveStates.length, state.allocation.amount);
                    const newShares = Math.floor(buyAmount / state.prices[day]);
                    if (newShares > 0) {
                        const buyCost = calculateTransactionCosts(buyAmount, true);
                        costs.totalBrokerage += buyCost.brokerage;
                        costs.totalSTT += buyCost.stt;
                        costs.totalStampDuty += buyCost.stampDuty;
                        costs.totalGST += buyCost.gst;
                        costs.totalCosts += buyCost.total;
                        totalTrades++;
                        cashReserve.value -= buyAmount + buyCost.total;
                        state.allocation = { ...state.allocation, shares: newShares, amount: newShares * state.prices[day] };
                        state.buyPrice = state.prices[day];
                        state.buyDayIdx = day;
                        state.active = true;
                    }
                }
            });
        }

        if (day > 0) {
            dailyReturns.push((portfolioValue - prevPortfolioValue) / prevPortfolioValue);
        }
        prevPortfolioValue = portfolioValue;

        // Record every ~5 days to keep equity curve manageable
        if (day === 0 || day % 5 === 0 || day === allDays) {
            equityCurve.push({
                date: dateStr,
                value: Math.round(portfolioValue),
                benchmark: Math.round(initialInvestment * (benchmarkPrices[day] / 100)),
            });
        }
    }

    // Compute final metrics
    const finalValue = equityCurve[equityCurve.length - 1].value;
    const totalReturn = ((finalValue - initialInvestment) / initialInvestment) * 100;
    const years = allDays / 365;
    const cagr = (Math.pow(finalValue / initialInvestment, 1 / Math.max(years, 0.1)) - 1) * 100;

    // Max drawdown
    let peak = equityCurve[0].value;
    let maxDD = 0;
    equityCurve.forEach(p => {
        if (p.value > peak) peak = p.value;
        const dd = (peak - p.value) / peak;
        if (dd > maxDD) maxDD = dd;
    });

    // Sharpe & Sortino
    const avgDR = dailyReturns.reduce((a, b) => a + b, 0) / Math.max(dailyReturns.length, 1);
    const stdDR = Math.sqrt(dailyReturns.reduce((s, r) => s + (r - avgDR) ** 2, 0) / Math.max(dailyReturns.length - 1, 1));
    const downReturns = dailyReturns.filter(r => r < 0);
    const downStd = downReturns.length > 1
        ? Math.sqrt(downReturns.reduce((s, r) => s + r ** 2, 0) / downReturns.length)
        : stdDR;
    const riskFreeDaily = 0.07 / 252;
    const sharpe = stdDR > 0 ? ((avgDR - riskFreeDaily) / stdDR) * Math.sqrt(252) : 0;
    const sortino = downStd > 0 ? ((avgDR - riskFreeDaily) / downStd) * Math.sqrt(252) : 0;
    const calmar = maxDD > 0 ? cagr / (maxDD * 100) : 0;
    const winRate = dailyReturns.filter(r => r > 0).length / Math.max(dailyReturns.length, 1) * 100;

    // Tax computation
    const ltcgTaxable = Math.max(0, taxes.ltcgGain - LTCG_EXEMPTION);
    taxes.ltcgTax = ltcgTaxable * LTCG_RATE;
    taxes.stcgTax = Math.max(0, taxes.stcgGain) * STCG_RATE;
    taxes.cessTax = (taxes.ltcgTax + taxes.stcgTax) * 0.04;
    taxes.totalTax = taxes.ltcgTax + taxes.stcgTax + taxes.cessTax;

    return {
        equityCurve,
        finalValue,
        totalReturn,
        cagr,
        maxDrawdown: maxDD * 100,
        sharpe,
        sortino,
        calmar,
        winRate,
        totalTrades,
        taxLiability: taxes,
        costBreakdown: costs,
        config,
        initialInvestment,
        notes: ['Local fallback uses GBM simulation and simplified tax/fee assumptions.'],
    };
}
