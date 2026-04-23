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
        ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-500'
        : inferredRegime === 'Bear'
            ? 'bg-rose-500/10 border-rose-500/20 text-rose-500'
            : 'bg-yellow-500/10 border-yellow-500/20 text-yellow-500';

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
            <div className="bg-[#141415] border border-[#2d2d2d] rounded-2xl p-4">
                <div className="flex items-center justify-between gap-4">
                    <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-xl bg-[#0a0a0a] border border-[#2d2d2d] flex items-center justify-center">
                            <Globe2 className="w-4 h-4 text-yellow-500" />
                        </div>
                        <div>
                            <h2 className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em]">Market Pulse</h2>
                            <p className="text-[10px] text-[#86868B] font-mono mt-1">
                                Blends local ingestion coverage with scored news semantics for sector momentum.
                            </p>
                        </div>
                    </div>
                    <button onClick={load} disabled={loading} className="bg-[#141415] border border-[#2d2d2d] font-semibold hover:bg-[#1d1d1f] transition-all px-4 py-2 text-[10px] uppercase tracking-[0.08em] flex items-center gap-2 text-[#f5f5f7] disabled:opacity-50">
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

            <div className={`bg-[#141415] border rounded-2xl p-4 ${inferredRegime === 'Bull' ? 'border-emerald-500/30' : inferredRegime === 'Bear' ? 'border-rose-500/30' : 'border-yellow-500/30'}`}>
                <div className="flex items-center justify-between gap-3">
                    <div>
                        <p className="text-[10px] uppercase tracking-[0.08em] font-bold text-[#86868B]">Market Regime</p>
                        <p className={`text-lg font-bold font-mono mt-1 ${inferredRegime === 'Bull' ? 'text-emerald-500' : inferredRegime === 'Bear' ? 'text-rose-500' : 'text-yellow-500'}`}>{inferredRegime}</p>
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
                <div className="lg:col-span-5 bg-[#141415] border border-[#2d2d2d] rounded-2xl p-5">
                    <div className="flex items-center gap-2 mb-4">
                        <TrendingUp className="w-4 h-4 text-emerald-500" />
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
                                    <span className="text-xs font-semibold text-[#f5f5f7] uppercase tracking-wide">{cell.sector}</span>
                                    <span className="text-xs font-bold font-mono" style={{ color: cell.color }}>
                                        {formatSentiment(cell.score)}
                                    </span>
                                </div>
                                <div className="h-1.5 rounded-full bg-[#0a0a0a] overflow-hidden">
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

                <div className="lg:col-span-7 bg-[#141415] border border-[#2d2d2d] rounded-2xl p-5 relative overflow-hidden">
                    <div className="absolute top-0 right-0 p-2">
                        <div className="w-2 h-2 rounded-full bg-rose-500 animate-pulse shadow-[0_0_8px_rgba(239,68,68,0.5)]"></div>
                    </div>
                    <div className="flex items-center gap-2 mb-4">
                        <ShieldAlert className="w-4 h-4 text-rose-500" />
                        <h3 className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em]">High-Impact Intelligence</h3>
                    </div>
                    <div className="space-y-4">
                        <div className="p-4 bg-rose-500/5 border border-rose-500/20 rounded-xl relative">
                            <h4 className="text-xs font-bold text-[#f5f5f7] mb-2 flex items-center gap-2">
                                <span className="w-1.5 h-1.5 rounded-full bg-rose-500"></span> Primary Market Driver
                            </h4>
                            <p className="text-sm text-[#f5f5f7] leading-relaxed mb-3">
                                {marketContext?.top_event_summary ?? 'Processing the latest high-impact macro headlines...'}
                            </p>
                            <div className="flex gap-4">
                                <div className="text-[9px] font-mono text-[#86868b] uppercase tracking-wider">Impact: <span className="text-rose-500 font-bold">CRITICAL</span></div>
                                <div className="text-[9px] font-mono text-[#86868b] uppercase tracking-wider">Source: <span className="text-[#f5f5f7]">Neural Aggregator</span></div>
                            </div>
                        </div>

                        <div className="space-y-3">
                            <p className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em]">Secondary Critical Factors</p>
                            {marketContext?.articles.slice(0, 3).map((article, idx) => (
                                <div key={idx} className="flex items-start gap-3 p-3 bg-[#0a0a0a] border border-[#2d2d2d] rounded-xl group hover:border-yellow-500/30 transition-all cursor-pointer">
                                    <div className="mt-1 w-1 h-1 rounded-full bg-yellow-500"></div>
                                    <div className="flex-1">
                                        <div className="text-[11px] font-bold text-[#f5f5f7] group-hover:text-yellow-500 transition-colors">{article.headline}</div>
                                        <div className="text-[10px] text-[#86868b] mt-0.5 line-clamp-1">{article.summary}</div>
                                    </div>
                                    <div className={`text-[9px] font-mono font-bold ${article.sentiment_score >= 0 ? 'text-emerald-500' : 'text-rose-500'}`}>
                                        {formatSentiment(article.sentiment_score)}
                                    </div>
                                </div>
                            ))}
                        </div>

                        <div className="space-y-1 pt-2 border-t border-[#2d2d2d]">
                             <p className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em] mb-2">Engine System Logs</p>
                            {(marketData?.notes ?? []).slice(0, 3).map((note, index) => (
                                <div key={index} className="text-[9px] font-mono text-[#6e6e73] flex items-center gap-2">
                                    <span className="text-[#2d2d2d]">•</span> {note}
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </div>

            <div className="bg-[#141415] border border-[#2d2d2d] rounded-2xl p-5">
                <div className="flex items-center gap-2 mb-4">
                    <Newspaper className="w-4 h-4 text-[#86868b]" />
                    <h3 className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em]">All News</h3>
                </div>
                <div className="space-y-3">
                    {(marketContext?.articles ?? []).map((article, index) => (
                        <div key={`${article.headline}-${index}`} className="rounded-xl border border-[#2d2d2d] bg-[#0a0a0a] px-4 py-3">
                            <div className="flex flex-wrap items-center gap-2 mb-2">
                                <span className="text-sm font-semibold text-[#f5f5f7]">{article.headline}</span>
                                <span className="text-[10px] bg-[#1d1d1f] text-[#86868b] px-2 py-0.5 rounded-full font-semibold">{article.source}</span>
                                <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${article.sentiment_score >= 0 ? 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-500 border border-rose-500/20'}`}>
                                    Sentiment {formatSentiment(article.sentiment_score)}
                                </span>
                                <span className="text-[10px] bg-[#1d1d1f] text-[#86868b] px-2 py-0.5 rounded-full font-semibold">Impact {article.impact_score.toFixed(1)}/10</span>
                            </div>
                            <p className="text-xs text-[#86868B] leading-relaxed mb-2">{article.summary}</p>
                            <div className="text-[10px] font-mono text-[#86868B]">
                                <span className="font-semibold text-[#f5f5f7]">Regions:</span> {article.involved_regions.join(', ')} · <span className="font-semibold text-[#f5f5f7]">Sectors:</span> {article.affected_sectors.join(', ')}
                            </div>
                            <div className="text-[10px] font-mono text-[#86868B] mt-1">{article.explanation}</div>
                            {article.url && (
                                <a href={article.url} target="_blank" rel="noreferrer" className="text-[10px] font-bold text-yellow-500 hover:text-yellow-600 uppercase tracking-wider mt-2 inline-block transition-colors">
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
