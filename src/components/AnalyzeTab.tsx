import React, { useRef, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { Plus, Search, Trash2, Info, ShieldCheck } from 'lucide-react';
import { AnalysisResult } from '../services/portfolioService';
import { analyzePortfolioViaApi } from '../services/backendApi';
import { NSE_STOCKS, LIQUID_ASSETS, SECTOR_CORRELATIONS } from '../data/stocks';
import { MetricCard, SectorChip } from './MetricCard';

const ALL_STOCKS = [...NSE_STOCKS, ...LIQUID_ASSETS];

function CorrelationMatrix({ sectors }: { sectors: string[] }) {
    if (sectors.length < 2) return null;
    const unique = [...new Set(sectors)];

    function heat(v: number): string {
        if (v >= 0.8) return '#ef4444';
        if (v >= 0.6) return '#f97316';
        if (v >= 0.4) return '#f59e0b';
        if (v >= 0.2) return '#84cc16';
        return '#10b981';
    }

    return (
        <div className="card p-4">
            <p className="section-title">Sector Correlation Matrix</p>
            <div className="overflow-x-auto">
                <table style={{ borderSpacing: '3px', borderCollapse: 'separate' }}>
                    <thead>
                        <tr>
                            <th className="w-16" />
                            {unique.map(s => (
                                <th key={s} className="text-center pb-1" style={{ minWidth: 56 }}>
                                    <span className="text-[9px] font-bold text-slate-600 uppercase tracking-wide">{s.slice(0, 4)}</span>
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {unique.map(row => (
                            <tr key={row}>
                                <td className="pr-2 text-right">
                                    <span className="text-[9px] font-bold text-slate-600 uppercase">{row.slice(0, 4)}</span>
                                </td>
                                {unique.map(col => {
                                    const v = SECTOR_CORRELATIONS[row]?.[col] ?? 0.5;
                                    return (
                                        <td key={col} className="p-0.5">
                                            <div
                                                className="heatmap-cell"
                                                style={{ background: heat(v) + '33', color: heat(v), border: `1px solid ${heat(v)}40` }}
                                                title={`${row} vs ${col}: ${v.toFixed(2)}`}
                                            >
                                                {v.toFixed(1)}
                                            </div>
                                        </td>
                                    );
                                })}
                            </tr>
                        ))}
                    </tbody>
                </table>
                <div className="flex gap-4 mt-3 text-xs text-slate-600">
                    {[['>=0.8', 'High', '#ef4444'], ['0.4-0.8', 'Mid', '#f59e0b'], ['<0.4', 'Low', '#10b981']].map(([r, l, c]) => (
                        <span key={r} className="flex items-center gap-1">
                            <span className="w-2.5 h-2.5 rounded-sm inline-block" style={{ background: c + '55', border: `1px solid ${c}` }} />
                            {r} - {l} corr
                        </span>
                    ))}
                </div>
            </div>
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
                <div className="card p-4">
                    <h2 className="font-mono text-[10px] uppercase tracking-wider font-bold flex items-center gap-2 mb-4">
                        <Plus className="w-4 h-4 text-blue-500" /> Add Holdings
                    </h2>

                    {analysisNotice && (
                        <p className="text-xs text-slate-500 mb-3">
                            {analysisNotice.text}
                        </p>
                    )}

                    <div className="mb-4">
                        <label className="block font-mono text-[10px] uppercase tracking-wider text-slate-600 mb-1">Paste portfolio (SYMBOL SHARES)</label>
                        <textarea
                            className="input-field px-3 py-2 text-xs h-24"
                            placeholder={'INFY 10\nHDFCBANK 8\nTCS,5'}
                            value={holdingsText}
                            onChange={(event) => {
                                analysisRequestId.current += 1;
                                setHoldingsText(event.target.value);
                                setResult(null);
                                setHoldings([]);
                                setAnalysisNotice(null);
                            }}
                        />
                        <button onClick={() => { void parseAndLoadHoldings(); }} className="btn-secondary mt-2 px-3 py-1.5 text-xs">
                            Analyze Posted Portfolio
                        </button>
                    </div>

                    <div className="relative w-full mb-3">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-600" />
                        <input
                            type="text"
                            className="w-full input-field pl-9 pr-4 py-2.5 text-sm"
                            placeholder="Search NSE stock..."
                            value={search}
                            onChange={e => { setSearch(e.target.value); setSelectedSym(''); }}
                        />
                        {filtered.length > 0 && (
                            <div className="absolute top-full left-0 mt-1 w-full z-50 bg-slate-800 border border-slate-700 rounded-sm max-h-60 overflow-y-auto">
                                {filtered.map(s => (
                                    <button
                                        key={s.symbol}
                                        onClick={() => { setSelectedSym(s.symbol); setSearch(s.symbol); }}
                                        className="w-full text-left px-4 py-2.5 hover:bg-slate-700/50 border-b border-slate-700 last:border-0"
                                    >
                                        <span className="font-bold text-sm text-slate-50">{s.symbol}</span>
                                        <span className="text-xs text-slate-600 ml-2">{s.name}</span>
                                        <span className="float-right"><SectorChip sector={s.sector} /></span>
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>

                    {(selectedSym || search.trim()) && (
                        <div className="flex gap-2 mb-3">
                            <div className="flex-1">
                                <input
                                    type="number"
                                    min={1}
                                    value={shares}
                                    onChange={e => setShares(Number(e.target.value))}
                                    className="input-field px-3 py-2 text-sm"
                                    placeholder="Shares"
                                />
                            </div>
                            <button onClick={addHolding} className="btn-primary px-4 py-2 text-sm">
                                <Plus className="w-4 h-4" />
                            </button>
                        </div>
                    )}

                    <div className="space-y-2 max-h-56 overflow-y-auto">
                        {holdings.length === 0 && (
                            <p className="text-sm text-slate-600 text-center py-4">No holdings added yet</p>
                        )}
                        {holdings.map(h => {
                            const stockData = ALL_STOCKS.find(s => s.symbol === h.symbol);
                            // Just use the backend total if it's 1 stock, or estimate it so the UI doesn't break
                            const displayValue = result ? (((result as any).portfolioValue || result.totalValue || 0) * (stockData?.price || 1) / 10000) : 0;
                            
                            return (
                                <div key={h.symbol} className="flex items-center justify-between p-3 bg-white border border-slate-200 rounded-xl mb-2">
                                    <div>
                                        <div className="font-bold text-sm text-slate-900">{h.symbol}</div>
                                        <div className="text-xs text-slate-500 font-mono">
                                            {h.shares} shares · Rs {displayValue > 0 ? displayValue.toLocaleString(undefined, { maximumFractionDigits: 2 }) : 'Loading live price...'}
                                        </div>
                                    </div>
                                    <button onClick={() => { void removeHolding(h.symbol); }} className="text-slate-400 hover:text-rose-600 transition-colors p-1">
                                        <Trash2 className="w-4 h-4" />
                                    </button>
                                </div>
                            );
                        })}
                    </div>
                </div>

            </div>

            <div className="lg:col-span-8 space-y-5">
                {!result ? (
                    <div className="card flex flex-col items-center justify-center text-slate-600 p-8 border border-dashed border-slate-600" style={{ minHeight: '400px' }}>
                        <Info className="w-12 h-12 mb-4 opacity-20" />
                        <p className="text-sm font-mono uppercase tracking-wider mb-1">{loadingAnalysis ? 'Analyzing holdings...' : 'Add your NSE holdings'}</p>
                        <p className="text-xs">We will assess risk, diversification, and sector correlation.</p>
                    </div>
                ) : (
                    <>
                        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                            <MetricCard label="Portfolio Value" value={`Rs ${(result.totalValue / 100000).toFixed(2)}L`} sub="At current prices" color="slate" />
                            <MetricCard
                                label="Weighted Beta"
                                value={result.riskScore.toFixed(2)}
                                sub="Market avg = 1.00"
                                color={result.riskScore > 1.3 ? 'red' : result.riskScore < 0.8 ? 'green' : 'blue'}
                                trend={result.riskScore > 1.3 ? 'up' : 'down'}
                            />
                            <MetricCard
                                label="Diversification"
                                value={`${result.diversificationScore.toFixed(0)}%`}
                                sub={`${Object.keys(result.sectorWeights).length} sectors`}
                                color={result.diversificationScore > 60 ? 'green' : result.diversificationScore > 40 ? 'amber' : 'red'}
                            />
                        </div>

                        <div className="card p-4">
                            <p className="section-title">Model Runtime</p>
                            <div className="runtime-grid grid grid-cols-2 md:grid-cols-3 gap-3 text-xs">
                                <div className="stat-row">
                                    <span className="stat-label">Variant Applied</span>
                                    <span className="stat-value">{result.modelVariantApplied || 'RULES'}</span>
                                </div>
                                <div className="stat-row">
                                    <span className="stat-label">Source</span>
                                    <span className="stat-value">{result.modelSource || 'RULES'}</span>
                                </div>
                                <div className="stat-row">
                                    <span className="stat-label">Mode</span>
                                    <span className="stat-value">{result.activeMode || 'rules_only'}</span>
                                </div>
                                <div className="stat-row">
                                    <span className="stat-label">ML Scores</span>
                                    <span className="stat-value">{Object.keys(result.mlPredictions || {}).length}</span>
                                </div>
                                <div className="stat-row">
                                    <span className="stat-label">Version</span>
                                    <span className="stat-value">{result.modelVersion || 'rules'}</span>
                                </div>
                                <div className="stat-row">
                                    <span className="stat-label">Artifact</span>
                                    <span className="stat-value">{result.artifactClassification || 'missing'}</span>
                                </div>
                                <div className="stat-row">
                                    <span className="stat-label">Review Cadence</span>
                                    <span className="stat-value">{result.holdingPeriodDaysRecommended || result.predictionHorizonDays || 21}D</span>
                                </div>
                            </div>
                            {result.holdingPeriodReason && (
                                <p className="text-xs text-slate-500 mt-3">{result.holdingPeriodReason}</p>
                            )}
                        </div>

                        <div className="space-y-2">
                            {result.suggestions.length === 0 ? (
                                <div className="flex items-center gap-2 text-[11px] font-mono tracking-wide text-slate-300">
                                    <ShieldCheck className="w-4 h-4 flex-shrink-0 text-emerald-500" />
                                    Portfolio looks well-balanced across sectors.
                                </div>
                            ) : result.suggestions.map((s, i) => (
                                <div key={i} className="flex items-center gap-2 text-[11px] font-mono tracking-wide text-slate-300">
                                    <Info className="w-4 h-4 flex-shrink-0 text-slate-600" /> {s}
                                </div>
                            ))}
                        </div>

                        {result.backendNotes && result.backendNotes.length > 0 && (
                            <div className="card p-4">
                                <p className="section-title">Analysis Notes</p>
                                <div className="space-y-2">
                                    {result.backendNotes.map((note, index) => (
                                        <p key={index} className="text-[11px] font-mono tracking-wide text-slate-300 leading-relaxed">{note}</p>
                                    ))}
                                </div>
                            </div>
                        )}

                        <div className="card p-4">
                            <p className="section-title">Sector Exposure</p>
                            <div className="h-52">
                                <ResponsiveContainer width="100%" height="100%">
                                    <BarChart data={sectorChartData}>
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} />
                                        <XAxis dataKey="name" fontSize={10} />
                                        <YAxis fontSize={10} unit="%" />
                                        <Tooltip formatter={(v: number) => [`${v}%`, 'Weight']} />
                                        <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                                            {sectorChartData.map((_, i) => (
                                                <Cell key={i} fill={i % 2 === 0 ? '#14b8a6' : '#3b82f6'} />
                                            ))}
                                        </Bar>
                                    </BarChart>
                                </ResponsiveContainer>
                            </div>
                        </div>

                        {factorChartData.length > 0 && (
                            <div className="card p-4">
                                <p className="section-title">Factor Exposures</p>
                                <div className="space-y-3">
                                    {factorChartData.map((item) => (
                                        <div key={item.name}>
                                            <div className="flex items-center justify-between text-[10px] mb-1">
                                                <span className="font-mono text-slate-600 uppercase tracking-wider">{item.name.replace('_', ' ')}</span>
                                                <span className={`font-mono ${item.value >= 0 ? 'text-emerald-500' : 'text-rose-500'}`}>{item.value >= 0 ? '+' : ''}{item.value.toFixed(2)}</span>
                                            </div>
                                            <div className="progress-bar-track">
                                                <div
                                                    className="progress-bar-fill"
                                                    style={{
                                                        width: `${Math.min(100, Math.abs(item.value) * 35)}%`,
                                                        background: item.value >= 0 ? '#14b8a6' : '#ef4444',
                                                    }}
                                                />
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {result.mlPredictions && Object.keys(result.mlPredictions).length > 0 && (
                            <div className="card p-4">
                                <p className="section-title">ML Scores By Holding</p>
                                <div className="space-y-2">
                                    {(Object.entries(result.mlPredictions) as [string, number][])
                                        .sort((left, right) => right[1] - left[1])
                                        .map(([symbol, score]) => (
                                            <div key={symbol} className="flex items-center justify-between p-3 bg-slate-800/50 rounded-sm border border-slate-700">
                                                <div>
                                                    <div className="font-bold text-sm font-mono text-slate-50">{symbol}</div>
                                                    {(result.topModelDriversBySymbol?.[symbol] || []).length > 0 && (
                                                        <div className="text-[9px] font-mono tracking-wider uppercase text-slate-600 mt-1">
                                                            {(result.topModelDriversBySymbol?.[symbol] || []).slice(0, 2).join(', ')}
                                                        </div>
                                                    )}
                                                </div>
                                                <span className={`font-mono text-sm ${score >= 0 ? 'text-emerald-500' : 'text-rose-500'}`}>
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
