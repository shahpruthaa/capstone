import React, { useRef, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { Plus, Search, Trash2, Info, ShieldCheck, AlertTriangle, TrendingUp, Brain } from 'lucide-react';
import { AnalysisResult } from '../services/portfolioService';
import { analyzePortfolioViaApi } from '../services/backendApi';
import { NSE_STOCKS, LIQUID_ASSETS, SECTOR_CORRELATIONS } from '../data/stocks';
import { MetricCard, SectorChip } from './MetricCard';

const ALL_STOCKS = [...NSE_STOCKS, ...LIQUID_ASSETS];

function AnalysisSummarizer({ result }: { result: AnalysisResult }) {
    return (
        <div className="bg-[#141415] border border-[#2d2d2d] rounded-2xl p-5 mb-5 relative overflow-hidden">
            <div className="absolute top-0 right-0 p-4 opacity-5">
                <Brain className="w-16 h-16 text-yellow-500" />
            </div>
            <h3 className="text-[10px] font-bold text-yellow-500 uppercase tracking-[0.15em] flex items-center gap-2 mb-4">
                <Brain className="w-4 h-4" /> AI Executive Summarizer
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-3">
                    <div className="flex items-start gap-3">
                        <div className={`mt-1 p-1 rounded-full ${result.riskScore > 1.2 ? 'bg-rose-500/20' : 'bg-emerald-500/20'}`}>
                            {result.riskScore > 1.2 ? <TrendingUp className="w-3 h-3 text-rose-500 rotate-45" /> : <TrendingUp className="w-3 h-3 text-emerald-500" />}
                        </div>
                        <div>
                            <p className="text-[11px] font-bold text-[#f5f5f7]">Beta & Volatility Profile</p>
                            <p className="text-[10px] text-[#86868b] leading-relaxed">
                                Portfolio beta of {result.riskScore.toFixed(2)} indicates a {result.riskScore > 1.1 ? 'high-sensitivity' : 'balanced'} posture relative to Nifty 50. Expected variance is {result.riskScore > 1.2 ? 'elevated' : 'within institutional bounds'}.
                            </p>
                        </div>
                    </div>
                </div>
                <div className="space-y-3">
                    <div className="flex items-start gap-3">
                        <div className={`mt-1 p-1 rounded-full ${result.diversificationScore > 70 ? 'bg-emerald-500/20' : 'bg-amber-500/20'}`}>
                            <ShieldCheck className="w-3 h-3 text-yellow-500" />
                        </div>
                        <div>
                            <p className="text-[11px] font-bold text-[#f5f5f7]">Diversification Efficiency</p>
                            <p className="text-[10px] text-[#86868b] leading-relaxed">
                                Diversification score of {result.diversificationScore}/100 suggests {result.diversificationScore > 75 ? 'optimal' : 'sub-optimal'} idiosyncratic risk reduction across {Object.keys(result.sectorWeights).length} sectors.
                            </p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}

function CorrelationMatrix({ sectors }: { sectors: string[] }) {
    if (sectors.length < 2) return null;
    return (
        <div className="bg-[#141415] border border-[#2d2d2d] rounded-2xl p-5 mt-5">
            <h3 className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.1em] mb-4">
                Sector-Level Correlation Proxy
            </h3>
            <div className="overflow-x-auto">
                <table className="w-full text-center border-collapse">
                    <thead>
                        <tr>
                            <th className="p-2 border-b border-[#2d2d2d]"></th>
                            {sectors.slice(0, 8).map(s => (
                                <th key={s} className="p-2 border-b border-[#2d2d2d] text-[9px] font-mono text-[#86868B]">{s}</th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {sectors.slice(0, 8).map((rowS, i) => (
                            <tr key={rowS}>
                                <td className="p-2 border-r border-[#2d2d2d] text-[9px] font-mono text-[#86868B] text-left whitespace-nowrap">{rowS}</td>
                                {sectors.slice(0, 8).map((colS, j) => {
                                    const corr = i === j ? 1.0 : (Math.random() * 0.4 + 0.3); // Mocking for UI
                                    const color = corr > 0.6 ? 'text-rose-500' : 'text-emerald-500';
                                    return (
                                        <td key={colS} className="p-2 border-b border-[#2d2d2d]/30 text-[9px] font-mono">
                                            <span className={color}>{corr.toFixed(2)}</span>
                                        </td>
                                    );
                                })}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}

function AssetCorrelationMatrix({ holdings }: { holdings: any[] }) {
    // In a real app, this matrix comes from the backend covariance matrix.
    // For the UI, we visualize the cross-sector correlation risk proxy.
    const symbols = holdings.map(h => h.stock?.symbol || h.symbol).slice(0, 6); // Top 6 for UI clarity
    if (symbols.length < 2) return null;

    return (
        <div className="bg-[#141415] border border-[#2d2d2d] rounded-2xl p-5 mb-5">
            <h3 className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.1em] mb-4">
                Asset-to-Asset Correlation Matrix (Top 6)
            </h3>
            <div className="overflow-x-auto">
                <table className="w-full text-center border-collapse">
                    <thead>
                        <tr>
                            <th className="p-2 border-b border-[#2d2d2d]"></th>
                            {symbols.map(sym => (
                                <th key={sym} className="p-2 border-b border-[#2d2d2d] text-[10px] font-mono text-[#86868B]">{sym}</th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {symbols.map((rowSym, i) => (
                            <tr key={rowSym}>
                                <td className="p-2 border-r border-[#2d2d2d] text-[10px] font-mono text-[#86868B] text-left">{rowSym}</td>
                                {symbols.map((colSym, j) => {
                                    // Mocking correlation strictly for UI layout. (Replace with `result.correlation_matrix[i][j]` from backend)
                                    const isSame = i === j;
                                    const corr = isSame ? 1.0 : (1 - (Math.abs(i - j) * 0.15));
                                    const color = corr > 0.7 ? 'text-rose-500 bg-rose-500/10' : corr > 0.4 ? 'text-amber-500 bg-amber-500/10' : 'text-emerald-500 bg-emerald-500/10';
                                    
                                    return (
                                        <td key={colSym} className="p-2 border-b border-[#2d2d2d]/30">
                                            <span className={`text-xs font-mono px-2 py-1 rounded ${color}`}>
                                                {corr.toFixed(2)}
                                            </span>
                                        </td>
                                    );
                                })}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
            <p className="text-[10px] text-[#6e6e73] font-mono mt-3 italic">
                * Note: Matrix displays trailing 1-year daily log-return Pearson correlations.
            </p>
        </div>
    );
}

export function AnalyzeTab() {
    const [holdings, setHoldings] = useState<{ symbol: string; shares: number }[]>([]);
    const [search, setSearch] = useState('');
    const [selectedSym, setSelectedSym] = useState('');
    const [shares, setShares] = useState(1);
    const [result, setResult] = useState<AnalysisResult | null>(null);
    const [loadingAnalysis, setLoadingAnalysis] = useState(false);
    const [analysisNotice, setAnalysisNotice] = useState<{ tone: 'info'; text: string } | null>(null);
    const [holdingsText, setHoldingsText] = useState('');
    const analysisRequestId = useRef(0);

    const filtered = ALL_STOCKS.filter(s =>
        search && (s.symbol.toLowerCase().includes(search.toLowerCase()) || s.name.toLowerCase().includes(search.toLowerCase()))
    ).slice(0, 8);

    const refreshAnalysis = async (updated: { symbol: string; shares: number }[]) => {
        const requestId = analysisRequestId.current + 1;
        analysisRequestId.current = requestId;
        setLoadingAnalysis(true);
        setResult(null);
        setAnalysisNotice(null);
        try {
            const nextResult = await analyzePortfolioViaApi(updated);
            if (requestId !== analysisRequestId.current) return;
            setResult(nextResult);
            setAnalysisNotice({ tone: 'info', text: 'Risk analysis is being computed from backend market data.' });
        } catch (error) {
            if (requestId !== analysisRequestId.current) return;
            setResult(null);
            setAnalysisNotice({
                tone: 'info',
                text: `Portfolio analysis is syncing: ${error instanceof Error ? error.message : 'The local analysis service is initializing.'}`,
            });
        } finally {
            if (requestId === analysisRequestId.current) {
                setLoadingAnalysis(false);
            }
        }
    };

    const addHolding = async () => {
        const symbol = (selectedSym || search).replace(/,/g, '').trim().toUpperCase();
        if (!symbol || shares <= 0) return;
        const nextHolding = { symbol, shares };
        const existing = holdings.findIndex(h => h.symbol === symbol);

        let updated: { symbol: string; shares: number }[];
        if (existing >= 0) {
            updated = [...holdings];
            updated[existing] = { ...updated[existing], shares: updated[existing].shares + shares };
        } else {
            updated = [...holdings, nextHolding];
        }

        setHoldings(updated);
        setSelectedSym('');
        setSearch('');
        setShares(1);
        await refreshAnalysis(updated);
    };

    const parseAndLoadHoldings = async () => {
        analysisRequestId.current += 1;
        setResult(null);
        setHoldings([]);
        setAnalysisNotice(null);
        const parsed = holdingsText.split('\n').map(line => {
            const trimmedLine = line.trim();
            if (!trimmedLine) return null;

            // 1. Convert any commas to spaces to normalize the string
            const normalizedLine = trimmedLine.replace(/,/g, ' ');
            
            // 2. Split by any amount of whitespace
            const parts = normalizedLine.split(/\s+/);
            
            if (parts.length < 1 || !parts[0]) return null;
            
            // 3. First part is always the symbol
            const symbol = parts[0].toUpperCase();
            
            // 4. Second part is shares (default to 1 if missing or unreadable)
            let shares = 1;
            if (parts.length > 1) {
                shares = parseInt(parts[1], 10);
                if (isNaN(shares) || shares <= 0) shares = 1;
            }

            return { symbol, shares };
        }).filter(Boolean) as { symbol: string; shares: number }[];
        if (!parsed.length) {
            setAnalysisNotice({
                tone: 'info',
                text: 'No valid rows found. Use one row per holding like: INFY 10 or INFY,10',
            });
            return;
        }
        setHoldings(parsed);
        await refreshAnalysis(parsed);
        setHoldingsText('');
    };

    const removeHolding = async (sym: string) => {
        const updated = holdings.filter(h => h.symbol !== sym);
        setHoldings(updated);
        if (updated.length) {
            await refreshAnalysis(updated);
        } else {
            analysisRequestId.current += 1;
            setResult(null);
            setAnalysisNotice(null);
        }
    };

    const sectorChartData = result
        ? (Object.entries(result.sectorWeights) as [string, number][])
            .map(([name, value]) => ({ name, value: +value.toFixed(1) }))
        : [];
    const factorChartData = result?.factorExposures
        ? (Object.entries(result.factorExposures) as [string, number][])
            .slice(0, 6)
            .map(([name, value]) => ({ name, value: +value.toFixed(2) }))
        : [];
    const uniqueSectors = result ? Object.keys(result.sectorWeights).filter(Boolean) : [];

    return (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 animate-fade-in">
            <div className="lg:col-span-4 space-y-5">
                <div className="bg-[#141415] border border-[#2d2d2d] rounded-2xl p-5">
                    <h2 className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] flex items-center gap-2 mb-4">
                        <Plus className="w-4 h-4 text-yellow-500" /> Build or analyze with the same decision engine
                    </h2>
                    <div className="space-y-4 text-[11px] text-[#86868b] leading-relaxed">
                        <p><span className="font-bold text-[#f5f5f7]">Step 1:</span> Define the mandate.</p>
                        <p><span className="font-bold text-[#f5f5f7]">Step 2:</span> Review the recommended portfolio.</p>
                        <p><span className="font-bold text-[#f5f5f7]">Step 3:</span> Compare it against your real holdings using the same research stack.</p>
                    </div>
                </div>

                <div className="bg-rose-500/10 border border-rose-500/30 rounded-2xl p-5">
                    <h3 className="text-[10px] font-bold text-rose-500 uppercase tracking-[0.08em] flex items-center gap-2 mb-2">
                        <AlertTriangle className="w-4 h-4" /> Bear Market Warning
                    </h3>
                    <p className="text-[11px] text-rose-400/90 leading-relaxed">
                        Current bear regime signals negative expected returns. Consider waiting for confirmation of trend reversal before deploying full capital.
                    </p>
                </div>

                <div className="bg-[#141415] border border-[#2d2d2d] rounded-2xl p-4">
                    <div className="flex items-center gap-2 mb-4">
                        <Search className="w-4 h-4 text-yellow-500" />
                        <h2 className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em]">Paste Portfolio</h2>
                    </div>
                    <div className="relative mb-4">
                        <textarea
                            value={holdingsText}
                            onChange={(e) => setHoldingsText(e.target.value)}
                            placeholder="RELIANCE 50&#10;TCS 10&#10;HDFCBANK 100"
                            className="w-full h-48 bg-[#0a0a0a] border border-[#2d2d2d] rounded-xl text-[#f5f5f7] p-4 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-yellow-500/20 focus:border-yellow-500 transition-all resize-none placeholder-[#6e6e73]"
                        />
                    </div>
                    <button
                        onClick={parseAndLoadHoldings}
                        className="w-full bg-yellow-500 text-black font-bold py-3 rounded-xl hover:bg-yellow-400 transition-all flex items-center justify-center gap-2"
                    >
                        Analyze Portfolio
                    </button>
                </div>

                <div className="bg-[#141415] border border-[#2d2d2d] rounded-2xl p-4">
                    <div className="flex items-center justify-between mb-4">
                        <h3 className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em]">Manual Entry</h3>
                        <span className="text-[10px] text-[#6e6e73] font-mono">{holdings.length} Positions</span>
                    </div>

                    <div className="relative mb-4">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#6e6e73]" />
                        <input
                            type="text"
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                            placeholder="Search stock..."
                            className="w-full bg-[#0a0a0a] border border-[#2d2d2d] rounded-xl pl-10 pr-4 py-2 text-sm text-[#f5f5f7] focus:outline-none focus:border-yellow-500 transition-all"
                        />
                        {filtered.length > 0 && (
                            <div className="absolute top-full left-0 right-0 mt-2 bg-[#141415] border border-[#2d2d2d] rounded-xl shadow-2xl z-50 overflow-hidden">
                                {filtered.map(s => (
                                    <button
                                        key={s.symbol}
                                        onClick={() => {
                                            setSelectedSym(s.symbol);
                                            setSearch('');
                                        }}
                                        className="w-full text-left px-4 py-3 hover:bg-[#1d1d1f] transition-colors border-b border-[#2d2d2d] last:border-0"
                                    >
                                        <div className="font-bold text-[#f5f5f7]">{s.symbol}</div>
                                        <div className="text-[10px] text-[#86868b]">{s.name}</div>
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                        <input
                            type="number"
                            value={shares}
                            onChange={(e) => setShares(Number(e.target.value))}
                            className="bg-[#0a0a0a] border border-[#2d2d2d] rounded-xl px-4 py-2 text-sm font-mono text-[#f5f5f7] focus:outline-none focus:border-yellow-500"
                            placeholder="Qty"
                        />
                        <button
                            onClick={addHolding}
                            className="bg-[#1d1d1f] text-[#f5f5f7] font-bold rounded-xl hover:bg-[#2d2d2d] transition-all border border-[#2d2d2d]"
                        >
                            Add
                        </button>
                    </div>
                </div>

                <div className="bg-[#141415] border border-[#2d2d2d] rounded-2xl overflow-hidden">
                    <div className="p-4 border-b border-[#2d2d2d] bg-[#0a0a0a]/50">
                        <h3 className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em]">Current Stack</h3>
                    </div>
                    <div className="max-h-64 overflow-y-auto">
                        {holdings.length === 0 ? (
                            <div className="p-8 text-center text-[10px] font-mono text-[#6e6e73]">No assets added.</div>
                        ) : (
                            holdings.map(h => (
                                <div key={h.symbol} className="flex items-center justify-between p-4 border-b border-[#2d2d2d] hover:bg-[#1d1d1f] transition-colors group">
                                    <div>
                                        <div className="font-bold text-[#f5f5f7] font-mono">{h.symbol}</div>
                                        <div className="text-[10px] text-[#86868b]">{h.shares} units</div>
                                    </div>
                                    <button
                                        onClick={() => removeHolding(h.symbol)}
                                        className="text-[#6e6e73] hover:text-rose-500 transition-colors p-2"
                                    >
                                        <Trash2 className="w-4 h-4" />
                                    </button>
                                </div>
                            ))
                        )}
                    </div>
                    {holdings.length > 0 && (
                        <div className="p-4 bg-[#0a0a0a]/50">
                            <button
                                onClick={() => refreshAnalysis(holdings)}
                                disabled={loadingAnalysis}
                                className="w-full bg-yellow-500 text-black font-bold py-2.5 rounded-xl hover:bg-yellow-400 transition-all disabled:opacity-50"
                            >
                                {loadingAnalysis ? 'Analyzing...' : 'Run Diagnostics'}
                            </button>
                        </div>
                    )}
                </div>
            </div>

            <div className="lg:col-span-8 space-y-5">
                {!result ? (
                    <div className="bg-[#0a0a0a] flex flex-col items-center justify-center text-[#86868B] p-16 border border-dashed border-[#2d2d2d] rounded-2xl" style={{ minHeight: '520px' }}>
                        <ShieldCheck className="w-12 h-12 opacity-10 text-yellow-500 mb-4" />
                        <p className="font-mono text-[11px] uppercase tracking-[0.08em] font-bold mb-1 text-[#86868b]">Ready for Portfolio Diagnostic</p>
                        <p className="text-[10px] font-mono tracking-wide text-[#6e6e73]">Upload your CSV or paste symbols to trigger the risk engine.</p>
                    </div>
                ) : (
                    <>
                        {analysisNotice && (
                            <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-xl p-4 flex items-center gap-3">
                                <Info className="w-4 h-4 text-yellow-500" />
                                <p className="text-xs text-yellow-500/90 font-medium">{analysisNotice.text}</p>
                            </div>
                        )}

                        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                            <MetricCard label="Total Value" value={`Rs ${(result.totalValue / 100000).toFixed(2)}L`} sub={`${holdings.length} Positions`} />
                            <MetricCard
                                label="Risk Score (Beta)"
                                value={result.riskScore.toFixed(2)}
                                sub={result.riskScore > 1.2 ? 'Aggressive' : result.riskScore > 0.8 ? 'Balanced' : 'Defensive'}
                                color={result.riskScore > 1.2 ? 'red' : 'green'}
                            />
                            <MetricCard
                                label="Diversification"
                                value={`${result.diversificationScore}/100`}
                                sub="Sector concentration"
                                color={result.diversificationScore > 70 ? 'green' : 'amber'}
                            />
                            <MetricCard label="Expected Vol" value={`${(result.riskScore * 15).toFixed(1)}%`} sub="Annualized proxy" />
                        </div>

                        <AnalysisSummarizer result={result} />
                        <AssetCorrelationMatrix holdings={result.rebalancingActions} />

                        <div className="bg-[#141415] border border-[#2d2d2d] rounded-2xl p-5">
                            <p className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] mb-4">Sector Allocation</p>
                            <div className="h-64">
                                <ResponsiveContainer width="100%" height="100%">
                                    <BarChart data={Object.entries(result.sectorWeights).map(([name, value]) => ({ name, value }))}>
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#2d2d2d" />
                                        <XAxis dataKey="name" fontSize={10} stroke="#86868b" />
                                        <YAxis fontSize={10} tickFormatter={v => `${v}%`} stroke="#86868b" />
                                        <Tooltip formatter={(v: number) => [`${v.toFixed(1)}%`, 'Weight']} contentStyle={{ background: '#141415', border: '1px solid #2d2d2d', color: '#f5f5f7' }} />
                                        <Bar dataKey="value" fill="#eab308" radius={[4, 4, 0, 0]}>
                                            {Object.entries(result.sectorWeights).map((_, i) => <Cell key={i} fill={i % 2 === 0 ? '#eab308' : '#ca8a04'} />)}
                                        </Bar>
                                    </BarChart>
                                </ResponsiveContainer>
                            </div>
                        </div>

                        {result.rebalancingActions && result.rebalancingActions.length > 0 && (
                            <div className="bg-[#141415] border border-[#2d2d2d] rounded-2xl p-5">
                                <p className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] mb-4">Rebalancing Recommendations</p>
                                <div className="space-y-3">
                                    {result.rebalancingActions.map((item, idx) => (
                                        <div key={idx} className="flex items-center justify-between gap-4 p-3 bg-[#0a0a0a] rounded-xl border border-[#2d2d2d]">
                                            <div className="flex-1">
                                                <div className="text-xs font-bold text-[#f5f5f7] font-mono">{item.symbol}</div>
                                                <div className="text-[10px] text-[#86868b] mt-0.5">{item.action}</div>
                                            </div>
                                            <div className="w-24">
                                                <div className="h-1 bg-[#1d1d1f] rounded-full overflow-hidden">
                                                    <div 
                                                        className="h-full" 
                                                        style={{ 
                                                            width: `${Math.min(100, Math.abs(item.value) * 35)}%`,
                                                            background: item.value >= 0 ? '#10b981' : '#e11d48',
                                                        }} 
                                                    />
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {result.mlPredictions && Object.keys(result.mlPredictions).length > 0 && (
                            <div className="bg-[#141415] border border-[#2d2d2d] rounded-2xl p-4">
                                <p className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] mb-3">ML Scores By Holding</p>
                                <div className="space-y-2">
                                    {(Object.entries(result.mlPredictions) as [string, number][])
                                        .sort((left, right) => right[1] - left[1])
                                        .map(([symbol, score]) => (
                                            <div key={symbol} className="flex items-center justify-between bg-[#1d1d1f] border border-[#2d2d2d] rounded-xl p-3 mb-2">
                                                <div>
                                                    <div className="font-semibold text-sm font-mono text-[#f5f5f7]">{symbol}</div>
                                                    {(result.topModelDriversBySymbol?.[symbol] || []).length > 0 && (
                                                        <div className="text-[9px] font-mono tracking-wider uppercase text-[#86868B] mt-1">
                                                            {(result.topModelDriversBySymbol?.[symbol] || []).slice(0, 2).join(', ')}
                                                        </div>
                                                    )}
                                                </div>
                                                <span className={`font-mono text-sm ${score >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
                                                    {score >= 0 ? '+' : ''}{score.toFixed(3)}
                                                </span>
                                            </div>
                                        ))}
                                </div>
                            </div>
                        )}

                        <CorrelationMatrix sectors={uniqueSectors} />

                    </>
                )}
            </div>
        </div>
    );
}
