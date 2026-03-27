import React, { useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { Plus, Search, Trash2, AlertTriangle, ShieldCheck, Zap, RefreshCw } from 'lucide-react';
import { AnalysisResult } from '../services/portfolioService';
import { analyzePortfolioViaApi } from '../services/backendApi';
import { NSE_STOCKS, LIQUID_ASSETS, SECTOR_CORRELATIONS } from '../data/stocks';
import { generateRebalancingAdvice } from '../services/localAdvisor';
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
        <div className="card p-5">
            <p className="section-title">Sector Correlation Matrix</p>
            <div className="overflow-x-auto">
                <table style={{ borderSpacing: '3px', borderCollapse: 'separate' }}>
                    <thead>
                        <tr>
                            <th className="w-16" />
                            {unique.map(s => (
                                <th key={s} className="text-center pb-1" style={{ minWidth: 56 }}>
                                    <span className="text-[9px] font-bold text-slate-400 uppercase tracking-wide">{s.slice(0, 4)}</span>
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {unique.map(row => (
                            <tr key={row}>
                                <td className="pr-2 text-right">
                                    <span className="text-[9px] font-bold text-slate-400 uppercase">{row.slice(0, 4)}</span>
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
                <div className="flex gap-4 mt-3 text-xs text-slate-400">
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
    const [aiAdvice, setAiAdvice] = useState('');
    const [loadingAI, setLoadingAI] = useState(false);
    const [loadingAnalysis, setLoadingAnalysis] = useState(false);
    const [analysisNotice, setAnalysisNotice] = useState<{ tone: 'info' | 'warning'; text: string } | null>(null);

    const filtered = ALL_STOCKS.filter(s =>
        search && (s.symbol.toLowerCase().includes(search.toLowerCase()) || s.name.toLowerCase().includes(search.toLowerCase()))
    ).slice(0, 8);

    const refreshAnalysis = async (updated: { symbol: string; shares: number }[]) => {
        setLoadingAnalysis(true);
        setAnalysisNotice(null);
        try {
            setResult(await analyzePortfolioViaApi(updated));
            setAnalysisNotice({ tone: 'info', text: 'Risk analysis is being computed from backend market data.' });
        } catch (error) {
            setResult(null);
            setAiAdvice('');
            setAnalysisNotice({
                tone: 'warning',
                text: `Portfolio analysis failed: ${error instanceof Error ? error.message : 'The local backend analysis endpoint is unavailable.'}`,
            });
        } finally {
            setLoadingAnalysis(false);
        }
    };

    const addHolding = async () => {
        if (!selectedSym) return;
        const nextHolding = { symbol: selectedSym, shares };
        const existing = holdings.findIndex(h => h.symbol === selectedSym);

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

    const removeHolding = async (sym: string) => {
        const updated = holdings.filter(h => h.symbol !== sym);
        setHoldings(updated);
        if (updated.length) {
            await refreshAnalysis(updated);
        } else {
            setResult(null);
        }
    };

    const getAIAdvice = async () => {
        if (!result) return;
        setLoadingAI(true);
        try {
            await new Promise(resolve => setTimeout(resolve, 250));
            setAiAdvice(generateRebalancingAdvice(holdings, result));
        } catch {
            setAiAdvice('Local rebalancing engine is temporarily unavailable.');
        } finally {
            setLoadingAI(false);
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

    const uniqueSectors = [...new Set(
        holdings.map(h => ALL_STOCKS.find(s => s.symbol === h.symbol)?.sector).filter(Boolean)
    )] as string[];

    return (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 animate-fade-in">
            <div className="lg:col-span-4 space-y-5">
                <div className="card p-6">
                    <h2 className="font-bold text-base flex items-center gap-2 mb-5">
                        <Plus className="w-4 h-4 text-teal-600" /> Add Holdings
                    </h2>

                    {analysisNotice && (
                        <div className={`${analysisNotice.tone === 'info' ? 'alert-info' : 'alert-warning'} text-xs mb-3`}>
                            {analysisNotice.text}
                        </div>
                    )}

                    <div className="relative mb-3">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                        <input
                            className="input-field pl-9 pr-4 py-2.5 text-sm"
                            placeholder="Search NSE stock..."
                            value={search}
                            onChange={e => { setSearch(e.target.value); setSelectedSym(''); }}
                        />
                        {filtered.length > 0 && (
                            <div className="absolute top-full left-0 w-full bg-white border border-slate-200 rounded-xl mt-1 shadow-xl z-20 max-h-48 overflow-y-auto">
                                {filtered.map(s => (
                                    <button
                                        key={s.symbol}
                                        onClick={() => { setSelectedSym(s.symbol); setSearch(s.symbol); }}
                                        className="w-full text-left px-4 py-2.5 hover:bg-slate-50 border-b border-slate-50 last:border-0"
                                    >
                                        <span className="font-bold text-sm text-slate-900">{s.symbol}</span>
                                        <span className="text-xs text-slate-400 ml-2">{s.name}</span>
                                        <span className="float-right"><SectorChip sector={s.sector} /></span>
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>

                    {selectedSym && (
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
                            <p className="text-sm text-slate-400 text-center py-4">No holdings added yet</p>
                        )}
                        {holdings.map(h => {
                            const stock = ALL_STOCKS.find(s => s.symbol === h.symbol);
                            return (
                                <div key={h.symbol} className="flex items-center justify-between p-3 bg-slate-50 rounded-xl border border-slate-100">
                                    <div>
                                        <div className="font-bold text-sm">{h.symbol}</div>
                                        <div className="text-xs text-slate-400">{h.shares} shares · Rs {((stock?.price || 0) * h.shares).toLocaleString()}</div>
                                    </div>
                                    <button onClick={() => { void removeHolding(h.symbol); }} className="text-slate-300 hover:text-rose-500 transition-colors p-1">
                                        <Trash2 className="w-4 h-4" />
                                    </button>
                                </div>
                            );
                        })}
                    </div>
                </div>

                {result && (
                    <div className="card p-5">
                        <h3 className="font-bold text-sm mb-3 flex items-center gap-2">
                            <Zap className="w-4 h-4 text-teal-600" /> Local Rebalancing Advice
                        </h3>
                        {aiAdvice ? (
                            <p className="text-sm text-slate-700 leading-relaxed whitespace-pre-line">{aiAdvice}</p>
                        ) : (
                            <p className="text-xs text-slate-400 mb-3">Generate local rebalancing guidance tailored to Indian market portfolios.</p>
                        )}
                        <button onClick={getAIAdvice} disabled={loadingAI} className="btn-primary px-4 py-2 text-xs flex items-center gap-2 mt-3">
                            {loadingAI ? <RefreshCw className="w-3 h-3 spin" /> : <RefreshCw className="w-3 h-3" />}
                            {aiAdvice ? 'Refresh Advice' : 'Get Advice'}
                        </button>
                    </div>
                )}
            </div>

            <div className="lg:col-span-8 space-y-5">
                {!result ? (
                    <div className="card flex flex-col items-center justify-center text-slate-400 p-16 border-2 border-dashed" style={{ minHeight: '400px' }}>
                        <AlertTriangle className="w-12 h-12 mb-4 opacity-20" />
                        <p className="text-base font-semibold mb-1">{loadingAnalysis ? 'Analyzing holdings...' : 'Add your NSE holdings'}</p>
                        <p className="text-sm">We will assess risk, diversification, and sector correlation.</p>
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

                        <div className="card p-5">
                            <p className="section-title">Model Runtime</p>
                            <div className="grid grid-cols-2 gap-3 text-xs">
                                <div className="stat-row">
                                    <span className="stat-label">Variant Applied</span>
                                    <span className="stat-value">{result.modelVariantApplied || 'RULES'}</span>
                                </div>
                                <div className="stat-row">
                                    <span className="stat-label">ML Scores</span>
                                    <span className="stat-value">{Object.keys(result.mlPredictions || {}).length}</span>
                                </div>
                            </div>
                        </div>

                        <div className="space-y-2">
                            {result.suggestions.length === 0 ? (
                                <div className="alert-success flex items-center gap-2">
                                    <ShieldCheck className="w-4 h-4 flex-shrink-0" />
                                    Portfolio looks well-balanced across sectors!
                                </div>
                            ) : result.suggestions.map((s, i) => (
                                <div key={i} className="alert-warning flex items-center gap-2">
                                    <AlertTriangle className="w-4 h-4 flex-shrink-0" /> {s}
                                </div>
                            ))}
                        </div>

                        <div className="card p-5">
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
                            <div className="card p-5">
                                <p className="section-title">Factor Exposures</p>
                                <div className="space-y-3">
                                    {factorChartData.map((item) => (
                                        <div key={item.name}>
                                            <div className="flex items-center justify-between text-xs mb-1">
                                                <span className="font-semibold text-slate-600 uppercase tracking-wide">{item.name.replace('_', ' ')}</span>
                                                <span className={`font-mono ${item.value >= 0 ? 'text-emerald-600' : 'text-rose-500'}`}>{item.value >= 0 ? '+' : ''}{item.value.toFixed(2)}</span>
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
                            <div className="card p-5">
                                <p className="section-title">ML Scores By Holding</p>
                                <div className="space-y-2">
                                    {(Object.entries(result.mlPredictions) as [string, number][])
                                        .sort((left, right) => right[1] - left[1])
                                        .map(([symbol, score]) => (
                                            <div key={symbol} className="flex items-center justify-between p-3 bg-slate-50 rounded-xl">
                                                <div>
                                                    <div className="font-bold text-sm text-slate-900">{symbol}</div>
                                                    {(result.topModelDriversBySymbol?.[symbol] || []).length > 0 && (
                                                        <div className="text-[10px] text-slate-500 mt-1">
                                                            {(result.topModelDriversBySymbol?.[symbol] || []).slice(0, 2).join(', ')}
                                                        </div>
                                                    )}
                                                </div>
                                                <span className={`font-mono text-sm ${score >= 0 ? 'text-emerald-600' : 'text-rose-500'}`}>
                                                    {score >= 0 ? '+' : ''}{score.toFixed(3)}
                                                </span>
                                            </div>
                                        ))}
                                </div>
                            </div>
                        )}

                        <CorrelationMatrix sectors={uniqueSectors} />

                        {result.rebalancingActions.length > 0 && (
                            <div className="card p-5">
                                <p className="section-title">Rebalancing Suggestions</p>
                                <div className="space-y-2">
                                    {result.rebalancingActions.slice(0, 5).map((a, i) => (
                                        <div key={i} className="flex items-center justify-between p-3 bg-slate-50 rounded-xl">
                                            <div>
                                                <span className="font-bold text-sm text-slate-900">{a.symbol}</span>
                                                <span className="text-xs text-slate-500 ml-2">{a.reason}</span>
                                            </div>
                                            <span className={`badge ${a.action === 'SELL' ? 'badge-red' : 'badge-green'}`}>{a.action}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </>
                )}
            </div>
        </div>
    );
}
