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
            <div className="card p-5" style={{ background: 'linear-gradient(135deg, rgba(20, 83, 45, 0.25), rgba(8, 47, 73, 0.18))', borderColor: 'rgba(125, 211, 252, 0.18)' }}>
                <div className="flex items-start justify-between gap-4">
                    <div>
                        <div className="flex items-center gap-2 mb-1">
                            <Globe2 className="w-4 h-4 text-sky-700" />
                            <h2 className="font-bold text-slate-900">Market Pulse</h2>
                        </div>
                        <p className="text-sm text-slate-600 leading-relaxed">
                            The Market tab now blends local ingestion coverage with scored news semantics so you can see what is moving sectors before it feeds into recommendations.
                        </p>
                    </div>
                    <button onClick={load} disabled={loading} className="btn-primary px-4 py-2 text-sm flex items-center gap-2">
                        <RefreshCw className={`w-4 h-4 ${loading ? 'spin' : ''}`} />
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

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <MetricCard label="Market Sentiment" value={marketContext ? formatSentiment(marketContext.overall_market_sentiment) : '--'} sub="News-derived composite" color={marketContext && marketContext.overall_market_sentiment >= 0 ? 'green' : 'amber'} trend={marketContext && marketContext.overall_market_sentiment >= 0 ? 'up' : 'down'} />
                <MetricCard label="Articles" value={String(marketContext?.articles.length ?? 0)} sub="Recent scored events" color="blue" />
                <MetricCard label="Instruments" value={String(marketData?.instrumentCount ?? 0)} sub={marketData?.available ? `Through ${marketData.maxTradeDate}` : 'Local DB not loaded'} color="slate" />
                <MetricCard label="Daily Bars" value={String(marketData?.dailyBarCount ?? 0)} sub={marketData?.minTradeDate ? `${marketData.minTradeDate} onwards` : 'No bars'} color="blue" />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
                <div className="lg:col-span-5 card p-5">
                    <div className="flex items-center gap-2 mb-3">
                        <TrendingUp className="w-4 h-4 text-emerald-600" />
                        <h3 className="font-bold text-slate-900">Sector Heatmap</h3>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        {heatmapCells.map((cell) => (
                            <div
                                key={cell.sector}
                                className="rounded-2xl border px-3 py-3"
                                style={{ background: cell.background, borderColor: cell.border }}
                            >
                                <div className="flex items-center justify-between gap-3 mb-2">
                                    <span className="text-sm font-semibold text-slate-800">{cell.sector}</span>
                                    <span className="text-sm font-semibold" style={{ color: cell.color }}>
                                        {formatSentiment(cell.score)}
                                    </span>
                                </div>
                                <div className="h-2 rounded-full bg-white/60 overflow-hidden">
                                    <div
                                        className="h-full rounded-full"
                                        style={{ width: cell.width, background: cell.color }}
                                    />
                                </div>
                            </div>
                        ))}
                        {!loading && heatmapCells.length === 0 && (
                            <div className="text-sm text-slate-500">No sector sentiment is available yet.</div>
                        )}
                    </div>
                </div>

                <div className="lg:col-span-7 card p-5">
                    <div className="flex items-center gap-2 mb-3">
                        <ShieldAlert className="w-4 h-4 text-amber-600" />
                        <h3 className="font-bold text-slate-900">Top Event</h3>
                    </div>
                    <p className="text-sm text-slate-700 leading-relaxed mb-4">
                        {marketContext?.top_event_summary ?? 'Loading the top event summary...'}
                    </p>
                    <div className="space-y-2 text-xs text-slate-500">
                        {(marketData?.notes ?? []).map((note, index) => (
                            <div key={index}>{note}</div>
                        ))}
                    </div>
                </div>
            </div>

            <div className="card p-5">
                <div className="flex items-center gap-2 mb-4">
                    <Newspaper className="w-4 h-4 text-slate-700" />
                    <h3 className="font-bold text-slate-900">All News</h3>
                </div>
                <div className="space-y-3">
                    {(marketContext?.articles ?? []).map((article, index) => (
                        <div key={`${article.headline}-${index}`} className="rounded-2xl border border-slate-100 bg-slate-50 px-4 py-3">
                            <div className="flex flex-wrap items-center gap-2 mb-2">
                                <span className="text-sm font-semibold text-slate-900">{article.headline}</span>
                                <span className="badge badge-neutral">{article.source}</span>
                                <span className={`badge ${article.sentiment_score >= 0 ? 'badge-green' : 'badge-red'}`}>
                                    Sentiment {formatSentiment(article.sentiment_score)}
                                </span>
                                <span className="badge badge-neutral">Impact {article.impact_score.toFixed(1)}/10</span>
                            </div>
                            <p className="text-sm text-slate-600 leading-relaxed mb-2">{article.summary}</p>
                            <div className="text-xs text-slate-500">
                                Regions: {article.involved_regions.join(', ')} · Sectors: {article.affected_sectors.join(', ')}
                            </div>
                            <div className="text-xs text-slate-400 mt-1">{article.explanation}</div>
                            {article.url && (
                                <a href={article.url} target="_blank" rel="noreferrer" className="text-xs text-sky-700 mt-2 inline-block">
                                    Open source
                                </a>
                            )}
                        </div>
                    ))}
                    {!loading && (marketContext?.articles.length ?? 0) === 0 && (
                        <div className="text-sm text-slate-500">No recent articles were available.</div>
                    )}
                </div>
            </div>
        </div>
    );
}
