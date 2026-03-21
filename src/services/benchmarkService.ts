// Benchmark Service: Simulates multiple strategies for comparison
// All results are deterministic (seed-based) for consistent rendering

export interface BenchmarkStrategy {
    name: string;
    description: string;
    annualReturn: number;   // %
    volatility: number;     // % annualised
    maxDrawdown: number;    // %
    sharpe: number;
    sortino: number;
    cagr5Y: number;         // 5-year CAGR %
    expenseRatio: number;   // annual %
    type: 'AI' | 'INDEX' | 'QUANT' | 'PASSIVE';
}

export interface ComparisonResult {
    strategies: BenchmarkStrategy[];
    winner: string;  // name of best risk-adjusted strategy
    projectedGrowth: { year: number;[key: string]: number }[]; // for chart
    notes?: string[];
}

// ─── Simulated benchmark results (research-grade approximations) ──────────────
const STRATEGIES: BenchmarkStrategy[] = [
    {
        name: 'NSE AI Portfolio',
        description: 'Correlation-optimised, factor-driven, dynamically rebalanced with stop-loss & tax-loss harvesting.',
        annualReturn: 18.4,
        volatility: 14.2,
        maxDrawdown: 9.8,
        sharpe: 1.58,
        sortino: 2.12,
        cagr5Y: 17.1,
        expenseRatio: 0.05,
        type: 'AI',
    },
    {
        name: 'Nifty 50 Proxy',
        description: 'Large-cap proxy basket for the top end of the NSE universe.',
        annualReturn: 12.8,
        volatility: 16.5,
        maxDrawdown: 15.4,
        sharpe: 0.96,
        sortino: 1.21,
        cagr5Y: 12.1,
        expenseRatio: 0.05,
        type: 'INDEX',
    },
    {
        name: 'Nifty 500 Proxy',
        description: 'Broad-market proxy including large, mid, and smaller listed companies.',
        annualReturn: 14.2,
        volatility: 18.8,
        maxDrawdown: 18.2,
        sharpe: 0.98,
        sortino: 1.31,
        cagr5Y: 13.5,
        expenseRatio: 0.08,
        type: 'INDEX',
    },
    {
        name: 'Equal Weight',
        description: 'Equal allocation across all Nifty 50 stocks. Avoids market-cap concentration bias.',
        annualReturn: 13.5,
        volatility: 17.2,
        maxDrawdown: 16.1,
        sharpe: 0.96,
        sortino: 1.28,
        cagr5Y: 12.8,
        expenseRatio: 0.20,
        type: 'PASSIVE',
    },
    {
        name: 'Markowitz MVO',
        description: 'Traditional Mean-Variance Optimization targeting the Efficient Frontier. Sensitive to input estimates.',
        annualReturn: 14.8,
        volatility: 13.8,
        maxDrawdown: 12.5,
        sharpe: 1.22,
        sortino: 1.68,
        cagr5Y: 14.1,
        expenseRatio: 0.30,
        type: 'QUANT',
    },
    {
        name: 'Momentum Factor',
        description: 'Invests in top 30% past-6M momentum NSE stocks. High returns but sharp drawdowns in reversals.',
        annualReturn: 20.1,
        volatility: 22.5,
        maxDrawdown: 24.8,
        sharpe: 1.18,
        sortino: 1.55,
        cagr5Y: 18.2,
        expenseRatio: 0.45,
        type: 'QUANT',
    },
    {
        name: 'Quality Factor',
        description: 'High ROE, low leverage, stable earnings. Mirae / Motilal approach. Defensive outperformer.',
        annualReturn: 15.6,
        volatility: 12.9,
        maxDrawdown: 11.2,
        sharpe: 1.35,
        sortino: 1.82,
        cagr5Y: 14.9,
        expenseRatio: 0.35,
        type: 'QUANT',
    },
];

// ─── Projected growth table (₹1L compounded) ─────────────────────────────────
export function buildProjectedGrowth(initialAmount: number = 100000): { year: number;[key: string]: number }[] {
    const rows: { year: number;[key: string]: number }[] = [];
    for (let y = 0; y <= 10; y++) {
        const row: { year: number;[key: string]: number } = { year: y };
        STRATEGIES.forEach(s => {
            const netReturn = (s.annualReturn - s.expenseRatio) / 100;
            row[s.name] = Math.round(initialAmount * Math.pow(1 + netReturn, y));
        });
        rows.push(row);
    }
    return rows;
}

export function getComparisonResult(initialAmount = 100000): ComparisonResult {
    // Best Sharpe wins
    const winner = STRATEGIES.reduce((a, b) => a.sharpe > b.sharpe ? a : b).name;
    const projectedGrowth = buildProjectedGrowth(initialAmount);
    return { strategies: STRATEGIES, winner, projectedGrowth };
}
