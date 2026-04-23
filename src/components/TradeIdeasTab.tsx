import React, { useEffect, useState } from 'react';
import { AlertTriangle, RefreshCw, ShieldCheck, Target, TrendingUp } from 'lucide-react';

import { TradeIdea, fetchTradeIdeasViaApi } from '../services/backendApi';
import { Portfolio } from '../services/portfolioService';
import { StockInsightDrawer } from './StockInsightDrawer';

function formatPct(value: number): string {
    return `${(value * 100).toFixed(1)}%`;
}

function TradeIdeaCard({ idea, onInspect }: { idea: TradeIdea; onInspect: (symbol: string) => void }) {
    const checklistItems = [
        { name: 'Regime aligned', check: idea.checklist.regime_check },
        { name: 'Sector strength', check: idea.checklist.sector_strength },
        { name: 'Relative strength', check: idea.checklist.relative_strength },
        { name: 'Technical setup', check: idea.checklist.technical_setup },
        { name: 'Options positioning', check: idea.checklist.options_positioning },
        { name: 'FII/DII flow', check: idea.checklist.fii_dii_flow },
        { name: 'Fundamental health', check: idea.checklist.fundamental_health },
        { name: 'Catalyst', check: idea.checklist.news_catalyst },
        { name: 'Entry / stop / target', check: idea.checklist.entry_stop_target },
        { name: 'Position sizing', check: idea.checklist.position_sizing },
    ];

    return (
        <div
            className="card p-5 cursor-pointer transition-colors hover:bg-slate-50 focus-visible:bg-slate-50"
            role="button"
            tabIndex={0}
            onClick={() => onInspect(idea.symbol)}
            onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    onInspect(idea.symbol);
                }
            }}
            aria-label={`Open AI stock insights for ${idea.symbol}`}
        >
            <div className="flex items-start justify-between gap-4 mb-3">
                <div>
                    <div className="flex items-center gap-2">
                        <h3 className="font-bold text-lg text-slate-900">
                            {idea.symbol}
                        </h3>
                        <span className="badge badge-neutral">{idea.sector}</span>
                        <span
                            className="badge badge-neutral"
                            style={idea.regime_alignment === 'aligned' ? { borderColor: 'rgba(16, 185, 129, 0.45)', color: '#10b981' } : undefined}
                        >
                            {idea.regime_alignment}
                        </span>
                    </div>
                    <p className="text-xs text-slate-500 mt-1">
                        Sector rank #{idea.sector_rank} · Expected annual return {formatPct(idea.expected_return_annual)}
                    </p>
                </div>
                <div className="text-right">
                    <div className="text-2xl font-bold text-slate-900">{idea.checklist_score}/10</div>
                    <div className="text-xs text-slate-500">Checklist score</div>
                </div>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                <div className="rounded-xl border border-slate-100 bg-slate-50 px-3 py-2">
                    <div className="text-[11px] uppercase tracking-wide text-slate-600">Entry</div>
                    <div className="font-semibold text-slate-900">Rs {idea.entry_price.toFixed(2)}</div>
                </div>
                <div className="rounded-xl border border-slate-100 bg-slate-50 px-3 py-2">
                    <div className="text-[11px] uppercase tracking-wide text-slate-600">Stop</div>
                    <div className="font-semibold text-slate-900">Rs {idea.stop_loss.toFixed(2)}</div>
                </div>
                <div className="rounded-xl border border-slate-100 bg-slate-50 px-3 py-2">
                    <div className="text-[11px] uppercase tracking-wide text-slate-600">Target</div>
                    <div className="font-semibold text-slate-900">Rs {idea.target_price.toFixed(2)}</div>
                </div>
                <div className="rounded-xl border border-slate-100 bg-slate-50 px-3 py-2">
                    <div className="text-[11px] uppercase tracking-wide text-slate-600">Risk / Reward</div>
                    <div className="font-semibold text-slate-900">{idea.risk_reward_ratio.toFixed(2)}:1</div>
                </div>
            </div>

            <div className="flex flex-wrap gap-3 text-sm text-slate-600 mb-4">
                <span className="flex items-center gap-1">
                    <Target className="w-4 h-4 text-teal-600" />
                    Size {idea.suggested_allocation_pct.toFixed(2)}% of portfolio
                </span>
                <span className="flex items-center gap-1">
                    <ShieldCheck className="w-4 h-4 text-amber-600" />
                    Max loss per unit Rs {idea.max_loss_per_unit.toFixed(2)}
                </span>
                {idea.catalyst && (
                    <span className="flex items-center gap-1">
                        <TrendingUp className="w-4 h-4 text-blue-600" />
                        Driver: {idea.catalyst}
                    </span>
                )}
            </div>

            <div className="space-y-2">
                {checklistItems.map(item => (
                    <div key={item.name} className="flex items-start gap-2 text-sm">
                        <span className={`mt-0.5 ${item.check.passed ? 'text-emerald-600' : 'text-amber-500'}`}>
                            {item.check.passed ? '✓' : '⚠'}
                        </span>
                        <div>
                            <div className={`font-medium ${item.check.passed ? 'text-slate-800' : 'text-slate-700'}`}>
                                {item.name}
                                <span className="ml-2 text-xs text-slate-600">({Math.round(item.check.score * 100)}%)</span>
                            </div>
                            <div className="text-xs leading-relaxed text-slate-500">{item.check.reason}</div>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}

export function TradeIdeasTab({ portfolio }: { portfolio: Portfolio | null }) {
    const [ideas, setIdeas] = useState<TradeIdea[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);
    const [drawerOpen, setDrawerOpen] = useState(false);

    const loadIdeas = async () => {
        setLoading(true);
        setError('');
        try {
            const response = await fetchTradeIdeasViaApi({ regimeAware: true, minChecklistScore: 7, maxIdeas: 8 });
            if (portfolio?.allocations.length) {
                const symbols = new Set(portfolio.allocations.map(allocation => allocation.stock.symbol));
                const filtered = response.filter((idea) => symbols.has(idea.symbol));
                setIdeas(filtered.length > 0 ? filtered : response);
            } else {
                setIdeas(response);
            }
        } catch (err) {
            setIdeas([]);
            setError(err instanceof Error ? err.message : 'Unable to load trade ideas right now.');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        void loadIdeas();
    }, [portfolio]);

    const openStockDrawer = (symbol: string) => {
        setSelectedSymbol(symbol);
        setDrawerOpen(true);
    };

    return (
        <div className="space-y-5">
            <div className="card p-5" style={{ background: 'linear-gradient(135deg, rgba(8, 145, 178, 0.18), rgba(15, 23, 42, 0.22))', borderColor: 'rgba(34, 211, 238, 0.18)' }}>
                <div className="flex items-start justify-between gap-4">
                    <div>
                        <div className="flex items-center gap-2 mb-1">
                            <Target className="w-4 h-4 text-cyan-700" />
                            <h2 className="font-bold text-slate-900">Decision Engine</h2>
                        </div>
                        <p className="text-sm text-slate-600 leading-relaxed">
                            Each idea is the human-readable version of the decision engine: regime fit, sector strength,
                            technical setup, risk framing, and the key news/geopolitical hook. When a portfolio is active,
                            we prioritize ideas that match the current basket.
                        </p>
                    </div>
                    <button onClick={loadIdeas} disabled={loading} className="btn-primary px-4 py-2 text-sm flex items-center gap-2">
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

            {loading && ideas.length === 0 && (
                <div className="card p-5 text-sm text-slate-500">Scanning the universe and assembling trade ideas...</div>
            )}

            {!loading && !error && ideas.length === 0 && (
                <div className="card p-5 text-sm text-slate-500">
                    No trade ideas cleared the current 7/10 checklist threshold. Try again after more market data is ingested or relax the filter in the API.
                </div>
            )}

            <div className="space-y-4">
                {ideas.map(idea => (
                    <div key={idea.symbol}>
                        <TradeIdeaCard idea={idea} onInspect={openStockDrawer} />
                    </div>
                ))}
            </div>
            <StockInsightDrawer
                symbol={selectedSymbol}
                open={drawerOpen}
                onClose={() => setDrawerOpen(false)}
            />
        </div>
    );
}
