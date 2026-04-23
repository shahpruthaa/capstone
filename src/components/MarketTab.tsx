import React, { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, Globe2, Newspaper, RefreshCw, ShieldAlert, TrendingUp } from 'lucide-react';

import {
    getMarketContextViaApi,
    getMarketDataSummaryViaApi,
    MarketContext,
    MarketDataSummary,
} from '../services/backendApi';
import { MetricCard } from './MetricCard';

function formatSentiment(value: number): string {
    return `${value >= 0 ? '+' : ''}${value.toFixed(2)}`;
}

export function MarketTab() {
    const [marketData, setMarketData] = useState<MarketDataSummary | null>(null);
    const [marketContext, setMarketContext] = useState<MarketContext | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    const load = async () => {
        setLoading(true);
        setError('');
        try {
            const [summary, context] = await Promise.all([
                getMarketDataSummaryViaApi(),
                getMarketContextViaApi(),
            ]);
            setMarketData(summary);
            setMarketContext(context);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Unable to load market context.');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        void load();
    }, []);

    const sectorHeatmap = useMemo(() => {
        if (!marketContext) return [];
        return (Object.entries(marketContext.sector_sentiment) as Array<[string, number]>)
            .sort((left, right) => Math.abs(right[1]) - Math.abs(left[1]))
            .slice(0, 12);
    }, [marketContext]);

    const usingFallbackNews = useMemo(
        () => (marketContext?.articles ?? []).length > 0 && (marketContext?.articles ?? []).every((article) => article.source === 'LocalFallback'),
        [marketContext],
    );

    const inferredRegime = useMemo(() => {
        const explicit = marketContext?.regime_name?.trim();
        if (explicit) return explicit;
        const score = marketContext?.overall_market_sentiment ?? 0;
        if (score >= 0.1) return 'Bull';
        if (score <= -0.1) return 'Bear';
        return 'Neutral';
    }, [marketContext]);

    const regimeTone = inferredRegime === 'Bull'
        ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
        : inferredRegime === 'Bear'
            ? 'bg-rose-50 border-rose-200 text-rose-800'
            : 'bg-amber-50 border-amber-200 text-amber-800';

    const heatmapCells = useMemo(() => {
        const maxAbs = Math.max(...sectorHeatmap.map(([, score]) => Math.abs(score)), 0.01);
        return sectorHeatmap.map(([sector, score]) => {
            const intensity = Math.max(0.18, Math.min(0.95, Math.abs(score) / maxAbs));
            const background = score >= 0
                ? `rgba(16, 185, 129, ${0.12 + intensity * 0.28})`
                : `rgba(239, 68, 68, ${0.12 + intensity * 0.28})`;
            const border = score >= 0 ? 'rgba(16, 185, 129, 0.38)' : 'rgba(239, 68, 68, 0.38)';
            const color = score >= 0 ? '#047857' : '#b91c1c';
            return { sector, score, background, border, color, width: `${Math.max(20, intensity * 100)}%` };
        });
    }, [sectorHeatmap]);

    return (
        <div className="space-y-5">
            <div className="bg-white border border-slate-200/80 rounded-2xl shadow-[0_2px_8px_rgb(0,0,0,0.04)] p-4">
                <div className="flex items-center justify-between gap-4">
                    <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-xl bg-slate-50 border border-slate-200 flex items-center justify-center">
                            <Globe2 className="w-4 h-4 text-blue-600" />
                        </div>
                        <div>
                            <h2 className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em]">Market Pulse</h2>
                            <p className="text-[10px] text-[#86868B] font-mono mt-1">
                                Blends local ingestion coverage with scored news semantics for sector momentum.
                            </p>
                        </div>
                    </div>
                    <button onClick={load} disabled={loading} className="bg-white border border-slate-200 rounded-xl font-semibold hover:bg-slate-50 transition-all shadow-sm px-4 py-2 text-[10px] uppercase tracking-[0.08em] flex items-center gap-2 text-slate-700 disabled:opacity-50">
                        <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'spin' : ''}`} />
                        Refresh
                    </button>
                </div>
            </div>

            {error && (
                <div className="alert-warning text-sm flex items-start gap-2">
                    <AlertTriangle className="w-4 h-4 mt-0.5" />
                    <span>{error}</span>
                </div>
            )}

            {usingFallbackNews && (
                <div className="alert-warning text-sm flex items-start gap-2">
                    <AlertTriangle className="w-4 h-4 mt-0.5" />
                    <span>Live market headlines could not be reached, so this view is temporarily using the deterministic local fallback feed.</span>
                </div>
            )}

            <div className={`bg-white border rounded-2xl shadow-[0_2px_8px_rgb(0,0,0,0.04)] p-4 ${inferredRegime === 'Bull' ? 'border-emerald-200' : inferredRegime === 'Bear' ? 'border-rose-200' : 'border-amber-200'}`}>
                <div className="flex items-center justify-between gap-3">
                    <div>
                        <p className="text-[10px] uppercase tracking-[0.08em] font-bold text-[#86868B]">Market Regime</p>
                        <p className={`text-lg font-bold font-mono mt-1 ${inferredRegime === 'Bull' ? 'text-emerald-600' : inferredRegime === 'Bear' ? 'text-rose-600' : 'text-amber-600'}`}>{inferredRegime}</p>
                    </div>
                    <div className="text-right text-[10px] text-[#86868B] font-mono">
                        <div>Generated: {marketContext?.generated_at ?? '--'}</div>
                        <div>Source: `/api/v1/news/market-context`</div>
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <MetricCard label="Market Sentiment" value={marketContext ? formatSentiment(marketContext.overall_market_sentiment) : '--'} sub="News-derived composite" color={marketContext && marketContext.overall_market_sentiment >= 0 ? 'green' : 'amber'} trend={marketContext && marketContext.overall_market_sentiment >= 0 ? 'up' : 'down'} />
                <MetricCard label="Articles" value={String(marketContext?.articles.length ?? 0)} sub="Recent scored events" color="blue" />
                <MetricCard label="Instruments" value={String(marketData?.instrumentCount ?? 0)} sub={marketData?.available ? `Through ${marketData.maxTradeDate}` : 'Local DB not loaded'} color="slate" />
                <MetricCard label="Daily Bars" value={String(marketData?.dailyBarCount ?? 0)} sub={marketData?.minTradeDate ? `${marketData.minTradeDate} onwards` : 'No bars'} color="blue" />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
                <div className="lg:col-span-5 bg-white border border-slate-200/80 rounded-2xl shadow-[0_2px_8px_rgb(0,0,0,0.04)] p-5">
                    <div className="flex items-center gap-2 mb-4">
                        <TrendingUp className="w-4 h-4 text-emerald-600" />
                        <h3 className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em]">Sector Heatmap</h3>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        {heatmapCells.map((cell) => (
                            <div
                                key={cell.sector}
                                className="rounded-xl border px-3 py-3"
                                style={{ background: cell.background, borderColor: cell.border }}
                            >
                                <div className="flex items-center justify-between gap-3 mb-2">
                                    <span className="text-xs font-semibold text-[#1D1D1F] uppercase tracking-wide">{cell.sector}</span>
                                    <span className="text-xs font-bold font-mono" style={{ color: cell.color }}>
                                        {formatSentiment(cell.score)}
                                    </span>
                                </div>
                                <div className="h-1.5 rounded-full bg-white/60 overflow-hidden">
                                    <div
                                        className="h-full rounded-full"
                                        style={{ width: cell.width, background: cell.color }}
                                    />
                                </div>
                            </div>
                        ))}
                        {!loading && heatmapCells.length === 0 && (
                            <div className="text-xs text-[#86868B] font-mono">No sector sentiment is available yet.</div>
                        )}
                    </div>
                </div>

                <div className="lg:col-span-7 bg-white border border-slate-200/80 rounded-2xl shadow-[0_2px_8px_rgb(0,0,0,0.04)] p-5">
                    <div className="flex items-center gap-2 mb-4">
                        <ShieldAlert className="w-4 h-4 text-amber-500" />
                        <h3 className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em]">Top Event</h3>
                    </div>
                    <p className="text-sm text-[#1D1D1F] leading-relaxed mb-4">
                        {marketContext?.top_event_summary ?? 'Loading the top event summary...'}
                    </p>
                    <div className="space-y-2 text-[10px] font-mono text-[#86868B]">
                        {(marketData?.notes ?? []).map((note, index) => (
                            <div key={index}>{note}</div>
                        ))}
                    </div>
                </div>
            </div>

            <div className="bg-white border border-slate-200/80 rounded-2xl shadow-[0_2px_8px_rgb(0,0,0,0.04)] p-5">
                <div className="flex items-center gap-2 mb-4">
                    <Newspaper className="w-4 h-4 text-slate-700" />
                    <h3 className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em]">All News</h3>
                </div>
                <div className="space-y-3">
                    {(marketContext?.articles ?? []).map((article, index) => (
                        <div key={`${article.headline}-${index}`} className="rounded-xl border border-slate-200/50 bg-slate-50/50 px-4 py-3">
                            <div className="flex flex-wrap items-center gap-2 mb-2">
                                <span className="text-sm font-semibold text-[#1D1D1F]">{article.headline}</span>
                                <span className="text-[10px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full font-semibold">{article.source}</span>
                                <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${article.sentiment_score >= 0 ? 'bg-emerald-50 text-emerald-600 border border-emerald-200/50' : 'bg-rose-50 text-rose-600 border border-rose-200/50'}`}>
                                    Sentiment {formatSentiment(article.sentiment_score)}
                                </span>
                                <span className="text-[10px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full font-semibold">Impact {article.impact_score.toFixed(1)}/10</span>
                            </div>
                            <p className="text-xs text-[#86868B] leading-relaxed mb-2">{article.summary}</p>
                            <div className="text-[10px] font-mono text-[#86868B]">
                                <span className="font-semibold text-[#1D1D1F]">Regions:</span> {article.involved_regions.join(', ')} · <span className="font-semibold text-[#1D1D1F]">Sectors:</span> {article.affected_sectors.join(', ')}
                            </div>
                            <div className="text-[10px] font-mono text-[#86868B] mt-1">{article.explanation}</div>
                            {article.url && (
                                <a href={article.url} target="_blank" rel="noreferrer" className="text-[10px] font-bold text-blue-600 hover:text-blue-700 uppercase tracking-wider mt-2 inline-block transition-colors">
                                    Open source
                                </a>
                            )}
                        </div>
                    ))}
                    {!loading && (marketContext?.articles.length ?? 0) === 0 && (
                        <div className="text-xs text-[#86868B] font-mono">No recent articles were available.</div>
                    )}
                </div>
            </div>
        </div>
    );
}
