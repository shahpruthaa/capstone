import React, { useEffect, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { Plus, Search, Trash2, Info, ShieldCheck, AlertTriangle } from 'lucide-react';
import { AnalysisResult } from '../services/portfolioService';
import { analyzePortfolioViaApi, getCurrentModelStatusViaApi, ModelVariant } from '../services/backendApi';
import { NSE_STOCKS, LIQUID_ASSETS, SECTOR_CORRELATIONS } from '../data/stocks';
import { MetricCard, SectorChip } from './MetricCard';
import { PortfolioFitBanner } from './PortfolioFitBanner';

const ALL_STOCKS = [...NSE_STOCKS, ...LIQUID_ASSETS];

function factorTiltLabel(value: number): string {
    const magnitude = Math.abs(value);
    if (magnitude < 0.15) return 'Near-neutral';
    if (magnitude < 0.35) return 'Small tilt';
    return 'Strong tilt';
}

function healthTone(label?: AnalysisResult['healthLabel']) {
    if (label === 'GOOD') {
        return {
            badge: 'bg-emerald-50 text-emerald-600 border border-emerald-200',
            icon: <ShieldCheck className="w-4 h-4 text-emerald-600" />,
        };
    }
    if (label === 'CAUTION') {
        return {
            badge: 'bg-rose-50 text-rose-500 border border-rose-200',
            icon: <AlertTriangle className="w-4 h-4 text-rose-500" />,
        };
    }
    return {
        badge: 'bg-amber-50 text-amber-600 border border-amber-200',
        icon: <Info className="w-4 h-4 text-amber-600" />,
    };
}

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
    const [loadingAnalysis, setLoadingAnalysis] = useState(false);
    const [analysisNotice, setAnalysisNotice] = useState<{ tone: 'info'; text: string } | null>(null);
    const [holdingsText, setHoldingsText] = useState('');
    const [activeModelVariant, setActiveModelVariant] = useState<ModelVariant>('RULES');

    useEffect(() => {
        const loadModelStatus = async () => {
            try {
                const status = await getCurrentModelStatusViaApi();
                setActiveModelVariant(status.available ? 'LIGHTGBM_HYBRID' : 'RULES');
            } catch {
                setActiveModelVariant('RULES');
            }
        };
        void loadModelStatus();
    }, []);

    const filtered = ALL_STOCKS.filter(s =>
        search && (s.symbol.toLowerCase().includes(search.toLowerCase()) || s.name.toLowerCase().includes(search.toLowerCase()))
    ).slice(0, 8);

    const refreshAnalysis = async (updated: { symbol: string; shares: number }[]) => {
        setLoadingAnalysis(true);
        setAnalysisNotice(null);
        try {
            setResult(await analyzePortfolioViaApi(updated, 'LOW_RISK', activeModelVariant));
            setAnalysisNotice({ tone: 'info', text: 'Risk analysis is being computed from backend market data.' });
        } catch (error) {
            setResult(null);
            setAnalysisNotice({
                tone: 'info',
                text: `Portfolio analysis is syncing: ${error instanceof Error ? error.message : 'The local analysis service is initializing.'}`,
            });
        } finally {
            setLoadingAnalysis(false);
        }
    };

    const addHolding = async () => {
        const symbol = (selectedSym || search).trim().toUpperCase();
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
        const rows = holdingsText
            .split('\n')
            .map((row) => row.trim())
            .filter(Boolean);
        const parsed: { symbol: string; shares: number }[] = [];
        for (const row of rows) {
            const [symbolRaw, sharesRaw] = row.split(/[,\s]+/).filter(Boolean);
            const symbol = (symbolRaw || '').toUpperCase();
            const sharesValue = Number(sharesRaw);
            if (!symbol || !Number.isFinite(sharesValue) || sharesValue <= 0) continue;
            parsed.push({ symbol, shares: Math.floor(sharesValue) });
        }
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
            setResult(null);
        }
    };

    const sectorChartData = result
        ? (Object.entries(result.sectorWeights) as [string, number][])
            .map(([name, value]) => ({ name, value: +value.toFixed(1) }))
            .sort((left, right) => right.value - left.value)
        : [];
    const factorChartData = result?.factorExposures
        ? (Object.entries(result.factorExposures) as [string, number][])
            .slice(0, 6)
            .map(([name, value]) => ({ name, value: +value.toFixed(2) }))
        : [];
    const diagnosisItems = result
        ? [
            { label: 'Risk', text: result.riskAssessment },
            { label: 'Diversification', text: result.diversificationAssessment },
            { label: 'Sector Concentration', text: result.concentrationAssessment },
            { label: 'Factors', text: result.factorAssessment },
            { label: 'Correlation', text: result.correlationAssessment },
            { label: 'Benchmark Fit', text: result.benchmarkAssessment },
            { label: 'Stock-Specific Risk', text: result.idiosyncraticRiskAssessment },
        ].filter((item): item is { label: string; text: string } => Boolean(item.text))
        : [];
    const actionItems = result?.recommendedActions?.length ? result.recommendedActions : result?.suggestions ?? [];
    const tone = healthTone(result?.healthLabel);

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
                        <p className="text-xs text-slate-500 mb-3">
                            {analysisNotice.text}
                        </p>
                    )}

                    <div className="mb-4">
                        <label className="block text-xs font-semibold text-slate-500 mb-1">Paste portfolio (SYMBOL SHARES)</label>
                        <textarea
                            className="input-field px-3 py-2 text-xs h-24"
                            placeholder={'INFY 10\nHDFCBANK 8\nTCS,5'}
                            value={holdingsText}
                            onChange={(event) => setHoldingsText(event.target.value)}
                        />
                        <button onClick={() => { void parseAndLoadHoldings(); }} className="btn-secondary mt-2 px-3 py-1.5 text-xs">
                            Analyze Pasted Portfolio
                        </button>
                    </div>

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

                    {(selectedSym || search.trim()) && (
                        <div className="flex gap-2 mb-3">
                            <div className="flex-1">
                                <input
                                    type="number"
                                    min={1}
                                    value={shares}
                                    onChange={e => setShares(Math.max(1, Math.floor(Number(e.target.value) || 1)))}
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
                            return (
                                <div key={h.symbol} className="flex items-center justify-between p-3 bg-slate-50 rounded-xl border border-slate-100">
                                    <div>
                                        <div className="font-bold text-sm">{h.symbol}</div>
                                        <div className="text-xs text-slate-400">{h.shares} shares</div>
                                    </div>
                                    <button onClick={() => { void removeHolding(h.symbol); }} className="text-slate-300 hover:text-rose-500 transition-colors p-1">
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
                    <div className="card flex flex-col items-center justify-center text-slate-400 p-16 border-2 border-dashed" style={{ minHeight: '400px' }}>
                        <Info className="w-12 h-12 mb-4 opacity-20" />
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
                                color={result.riskScore > 1.15 ? 'red' : result.riskScore < 0.85 ? 'green' : 'blue'}
                                trend={result.riskScore > 1.1 ? 'up' : result.riskScore < 0.9 ? 'down' : 'flat'}
                            />
                            <MetricCard
                                label="Diversification"
                                value={`${result.diversificationScore.toFixed(0)}%`}
                                sub={`${Object.keys(result.sectorWeights).length} sectors`}
                                color={result.diversificationScore >= 75 ? 'green' : result.diversificationScore >= 55 ? 'amber' : 'red'}
                            />
                        </div>

                        <PortfolioFitBanner summary={result.portfolioFitSummary} />

                        {(result.healthSummary || diagnosisItems.length > 0) && (
                            <div className="card p-5">
                                <div className="flex flex-col gap-4">
                                    <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-3">
                                        <div>
                                            <p className="section-title">Portfolio Health</p>
                                            {result.healthSummary && (
                                                <p className="text-sm text-slate-600 leading-relaxed">{result.healthSummary}</p>
                                            )}
                                        </div>
                                        {result.healthLabel && (
                                            <span className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold w-fit ${tone.badge}`}>
                                                {tone.icon}
                                                {result.healthLabel}
                                            </span>
                                        )}
                                    </div>

                                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                                        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
                                            <p className="text-[11px] uppercase tracking-wide text-slate-400 font-semibold mb-1">Breadth</p>
                                            <p className="text-lg font-bold text-slate-900">{result.totalHoldings ?? holdings.length} holdings</p>
                                            <p className="text-xs text-slate-500">Spread across {Object.keys(result.sectorWeights).length} sectors</p>
                                        </div>
                                        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
                                            <p className="text-[11px] uppercase tracking-wide text-slate-400 font-semibold mb-1">Largest Sector</p>
                                            <p className="text-lg font-bold text-slate-900">{result.largestSector || 'N/A'}</p>
                                            <p className="text-xs text-slate-500">{(result.largestSectorWeight ?? 0).toFixed(1)}% of portfolio</p>
                                        </div>
                                        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
                                            <p className="text-[11px] uppercase tracking-wide text-slate-400 font-semibold mb-1">Avg Correlation</p>
                                            <p className="text-lg font-bold text-slate-900">{(result.avgPairwiseCorrelation ?? 0).toFixed(2)}</p>
                                            <p className="text-xs text-slate-500">Lower numbers improve diversification</p>
                                        </div>
                                    </div>

                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                        {diagnosisItems.map((item) => (
                                            <div key={item.label} className="rounded-2xl border border-slate-200 bg-white p-4">
                                                <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-2">{item.label}</p>
                                                <p className="text-sm text-slate-600 leading-relaxed">{item.text}</p>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            </div>
                        )}

                        <div className="card p-5">
                            <p className="section-title">Review Cadence</p>
                            <div className="runtime-grid grid grid-cols-2 md:grid-cols-3 gap-3 text-xs">
                                <div className="stat-row">
                                    <span className="stat-label">Review every</span>
                                    <span className="stat-value">{result.holdingPeriodDaysRecommended || result.predictionHorizonDays || 21}D</span>
                                </div>
                                <div className="stat-row">
                                    <span className="stat-label">Priced holdings</span>
                                    <span className="stat-value">{result.totalHoldings ?? holdings.length}</span>
                                </div>
                                <div className="stat-row">
                                    <span className="stat-label">Scored holdings</span>
                                    <span className="stat-value">{Object.keys(result.mlPredictions || {}).length}</span>
                                </div>
                            </div>
                            {result.holdingPeriodReason && (
                                <p className="text-xs text-slate-500 mt-3">{result.holdingPeriodReason}</p>
                            )}
                        </div>

                        <div className="card p-5">
                            <p className="section-title">Recommended Actions</p>
                            {result.rebalanceSummary && (
                                <p className="text-sm text-slate-600 leading-relaxed mb-3">{result.rebalanceSummary}</p>
                            )}
                            <div className="space-y-2">
                                {actionItems.length === 0 ? (
                                    <div className="flex items-center gap-2 text-sm text-slate-600">
                                        <ShieldCheck className="w-4 h-4 flex-shrink-0 text-teal-600" />
                                        Portfolio is within the current guardrails.
                                    </div>
                                ) : actionItems.map((s, i) => (
                                    <div key={i} className="flex items-start gap-2 text-sm text-slate-600">
                                        <Info className="w-4 h-4 flex-shrink-0 text-slate-400 mt-0.5" />
                                        <span>{s}</span>
                                    </div>
                                ))}
                            </div>

                            {result.rebalancingActions.length > 0 && (
                                <div className="mt-4 space-y-2">
                                    {result.rebalancingActions.slice(0, 4).map((action) => (
                                        <div key={`${action.symbol}-${action.action}`} className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
                                            <div className="flex items-center justify-between gap-3">
                                                <div className="font-bold text-sm text-slate-900">{action.symbol}</div>
                                                <span className={`text-[11px] font-semibold uppercase tracking-wide ${action.action === 'SELL' ? 'text-rose-500' : action.action === 'BUY' ? 'text-emerald-600' : 'text-slate-500'}`}>
                                                    {action.action}
                                                </span>
                                            </div>
                                            <p className="text-xs text-slate-500 mt-1">
                                                Current {action.currentWeight.toFixed(1)}% · Target {action.targetWeight.toFixed(1)}%
                                            </p>
                                            <p className="text-sm text-slate-600 mt-2 leading-relaxed">{action.reason}</p>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>

                        {result.backendNotes && result.backendNotes.length > 0 && (
                            <div className="card p-5">
                                <p className="section-title">Analysis Notes</p>
                                <div className="space-y-2">
                                    {result.backendNotes.map((note, index) => (
                                        <p key={index} className="text-xs text-slate-600 leading-relaxed">{note}</p>
                                    ))}
                                </div>
                            </div>
                        )}

                        <div className="card p-5">
                            <p className="section-title">Sector Exposure</p>
                            {sectorChartData.length > 0 && (
                                <div className="flex flex-wrap gap-2 mb-4">
                                    {sectorChartData.map((item) => (
                                        <div key={item.name} className="flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5">
                                            <SectorChip sector={item.name} />
                                            <span className="text-xs font-mono text-slate-500">{item.value.toFixed(1)}%</span>
                                        </div>
                                    ))}
                                </div>
                            )}
                            <div className="h-52">
                                <ResponsiveContainer width="100%" height="100%">
                                    <BarChart data={sectorChartData} margin={{ top: 8, right: 12, left: -12, bottom: 24 }}>
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} />
                                        <XAxis
                                            dataKey="name"
                                            fontSize={10}
                                            interval={0}
                                            minTickGap={0}
                                            angle={-18}
                                            textAnchor="end"
                                            height={52}
                                            tickLine={false}
                                            axisLine={false}
                                        />
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
                                {result.factorAssessment && (
                                    <p className="text-sm text-slate-600 leading-relaxed mb-4">{result.factorAssessment}</p>
                                )}
                                <div className="space-y-3">
                                    {factorChartData.map((item) => (
                                        <div key={item.name}>
                                            <div className="flex items-center justify-between text-xs mb-1">
                                                <span className="font-semibold text-slate-600 uppercase tracking-wide">{item.name.replace('_', ' ')}</span>
                                                <div className="flex items-center gap-2">
                                                    <span className="text-[10px] uppercase tracking-wide text-slate-400">{factorTiltLabel(item.value)}</span>
                                                    <span className={`font-mono ${item.value >= 0 ? 'text-emerald-600' : 'text-rose-500'}`}>{item.value >= 0 ? '+' : ''}{item.value.toFixed(2)}</span>
                                                </div>
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

                        {result.correlationAssessment && (
                            <div className="card p-5">
                                <p className="section-title">Correlation Insight</p>
                                <p className="text-sm text-slate-600 leading-relaxed">{result.correlationAssessment}</p>
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

                    </>
                )}
            </div>
        </div>
    );
}
