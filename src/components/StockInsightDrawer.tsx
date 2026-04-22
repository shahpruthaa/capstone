import React, { useEffect, useMemo, useState } from 'react';
import { BrainCircuit, Loader2, Network, ShieldAlert, X } from 'lucide-react';

import { getStockDetailViaApi, StockDetail } from '../services/backendApi';

function formatPct(value: number): string {
    return `${value >= 0 ? '+' : ''}${(value * 100).toFixed(2)}%`;
}

function splitExplanation(text: string): string[] {
    const trimmed = text.trim();
    if (!trimmed) return [];
    const byParagraph = trimmed.split(/\n\s*\n/).map((part) => part.trim()).filter(Boolean);
    if (byParagraph.length > 1) return byParagraph;
    return trimmed
        .split(/(?<=[.!?])\s+(?=[A-Z])/)
        .map((part) => part.trim())
        .filter(Boolean);
}

interface Props {
    symbol: string | null;
    open: boolean;
    onClose: () => void;
}

export function StockInsightDrawer({ symbol, open, onClose }: Props) {
    const [detail, setDetail] = useState<StockDetail | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    useEffect(() => {
        if (!open || !symbol) return;
        const load = async () => {
            setLoading(true);
            setError('');
            try {
                const response = await getStockDetailViaApi(symbol);
                if (response.error) {
                    throw new Error(response.error);
                }
                setDetail(response);
            } catch (err) {
                setDetail(null);
                setError(err instanceof Error ? err.message : `Could not load stock detail for ${symbol}.`);
            } finally {
                setLoading(false);
            }
        };
        void load();
    }, [open, symbol]);

    const explanationParagraphs = useMemo(
        () => splitExplanation(detail?.explanation || ''),
        [detail?.explanation],
    );

    if (!open || !symbol) return null;

    return (
        <div className="fixed inset-0 z-[80]">
            <button
                type="button"
                onClick={onClose}
                className="absolute inset-0 bg-slate-900/35"
                aria-label="Close stock insight panel"
            />
            <aside className="absolute right-0 top-0 h-full w-full max-w-2xl overflow-y-auto border-l border-slate-200 bg-white shadow-2xl">
                <div className="sticky top-0 z-10 border-b border-slate-200 bg-white/95 px-6 py-4 backdrop-blur">
                    <div className="flex items-start justify-between gap-3">
                        <div>
                            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">AI Stock Evaluator</p>
                            <h3 className="text-xl font-bold text-slate-900">{symbol}</h3>
                            <p className="text-xs text-slate-500">/api/v1/stock/{symbol}</p>
                        </div>
                        <button
                            type="button"
                            onClick={onClose}
                            className="rounded-full border border-slate-200 bg-white p-2 text-slate-600 hover:bg-slate-50"
                            aria-label="Close"
                        >
                            <X className="h-4 w-4" />
                        </button>
                    </div>
                </div>

                <div className="space-y-5 p-6">
                    {loading && (
                        <div className="space-y-5 animate-pulse">
                            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                                {Array.from({ length: 6 }).map((_, idx) => (
                                    <div key={idx} className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3">
                                        <div className="h-3 w-16 rounded bg-slate-200 mb-2" />
                                        <div className="h-4 w-20 rounded bg-slate-300" />
                                    </div>
                                ))}
                            </div>

                            <div className="card p-5">
                                <div className="h-4 w-44 rounded bg-slate-200 mb-3" />
                                <div className="space-y-2">
                                    {Array.from({ length: 4 }).map((_, idx) => (
                                        <div key={idx} className="h-10 rounded-xl bg-slate-100 border border-slate-200" />
                                    ))}
                                </div>
                            </div>

                            <div className="card p-5">
                                <div className="h-4 w-40 rounded bg-slate-200 mb-3" />
                                <div className="space-y-2">
                                    <div className="h-3 w-full rounded bg-slate-100" />
                                    <div className="h-3 w-full rounded bg-slate-100" />
                                    <div className="h-3 w-4/5 rounded bg-slate-100" />
                                    <div className="h-3 w-full rounded bg-slate-100 mt-3" />
                                    <div className="h-3 w-11/12 rounded bg-slate-100" />
                                </div>
                            </div>

                            <div className="card p-5">
                                <div className="h-4 w-36 rounded bg-slate-200 mb-3" />
                                <div className="space-y-2">
                                    {Array.from({ length: 5 }).map((_, idx) => (
                                        <div key={idx} className="h-6 rounded bg-slate-100 border border-slate-200" />
                                    ))}
                                </div>
                            </div>

                            <div className="text-xs text-slate-500 flex items-center gap-2">
                                <Loader2 className="h-4 w-4 spin" />
                                Running ensemble inference and fiduciary evaluation...
                            </div>
                        </div>
                    )}

                    {!loading && error && (
                        <div className="alert-warning text-sm">{error}</div>
                    )}

                    {!loading && !error && detail && (
                        <>
                            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                                <div className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3">
                                    <p className="text-[11px] uppercase tracking-wide text-slate-400">Sector</p>
                                    <p className="text-sm font-semibold text-slate-900">{detail.sector}</p>
                                </div>
                                <div className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3">
                                    <p className="text-[11px] uppercase tracking-wide text-slate-400">Annual Forecast</p>
                                    <p className="text-sm font-semibold text-slate-900">{formatPct(detail.pred_annual_return)}</p>
                                </div>
                                <div className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3">
                                    <p className="text-[11px] uppercase tracking-wide text-slate-400">Death Risk</p>
                                    <p className="text-sm font-semibold text-slate-900">{detail.death_risk.toFixed(2)}</p>
                                </div>
                                <div className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3">
                                    <p className="text-[11px] uppercase tracking-wide text-slate-400">Ensemble Score</p>
                                    <p className="text-sm font-semibold text-slate-900">{formatPct(detail.ensemble_score)}</p>
                                </div>
                                <div className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3">
                                    <p className="text-[11px] uppercase tracking-wide text-slate-400">Beta</p>
                                    <p className="text-sm font-semibold text-slate-900">{detail.beta.toFixed(2)}</p>
                                </div>
                                <div className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3">
                                    <p className="text-[11px] uppercase tracking-wide text-slate-400">As Of</p>
                                    <p className="text-sm font-semibold text-slate-900">{detail.as_of_date}</p>
                                </div>
                            </div>

                            <div className="card p-5">
                                <div className="flex items-center gap-2 mb-3">
                                    <BrainCircuit className="h-4 w-4 text-blue-600" />
                                    <h4 className="font-bold text-slate-900">Quantitative Drivers</h4>
                                </div>
                                <div className="space-y-2 text-sm text-slate-700">
                                    {(detail.feature_drivers.length > 0 ? detail.feature_drivers : ['No top drivers provided by the engine.']).map((driver, idx) => (
                                        <div key={`${driver}-${idx}`} className="rounded-xl border border-slate-100 bg-slate-50 px-3 py-2">{driver}</div>
                                    ))}
                                </div>
                                {detail.model_components.length > 0 && (
                                    <p className="text-xs text-slate-500 mt-3">
                                        Active weights: {detail.model_components.join(' | ')}
                                    </p>
                                )}
                            </div>

                            <div className="card p-5">
                                <div className="flex items-center gap-2 mb-3">
                                    <ShieldAlert className="h-4 w-4 text-amber-600" />
                                    <h4 className="font-bold text-slate-900">Fiduciary Evaluation</h4>
                                </div>
                                <div className="space-y-3 text-sm text-slate-700 leading-relaxed">
                                    {(explanationParagraphs.length > 0 ? explanationParagraphs : ['No narrative explanation returned by the evaluator.']).map((paragraph, index) => (
                                        <p key={index}>{paragraph}</p>
                                    ))}
                                </div>
                            </div>

                            <div className="card p-5">
                                <div className="flex items-center gap-2 mb-3">
                                    <Network className="h-4 w-4 text-emerald-600" />
                                    <h4 className="font-bold text-slate-900">Topology Context</h4>
                                </div>
                                <p className="text-sm text-slate-700 mb-3">
                                    Sector neighbors: {detail.gnn_sector_neighbors.length > 0 ? detail.gnn_sector_neighbors.join(', ') : 'None available'}
                                </p>
                                <div className="space-y-1 text-xs text-slate-500">
                                    {Object.entries(detail.factor_scores || {}).slice(0, 8).map(([name, value]) => (
                                        <div key={name} className="stat-row py-1">
                                            <span className="stat-label">{name}</span>
                                            <span className="stat-value">{Number(value).toFixed(4)}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </>
                    )}
                </div>
            </aside>
        </div>
    );
}
