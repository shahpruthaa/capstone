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
            className="bg-[#141415] border border-[#2d2d2d] rounded-2xl p-5 cursor-pointer transition-colors hover:bg-[#1d1d1f] focus-visible:bg-[#1d1d1f]"
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
                        <h3 className="font-bold text-lg text-[#f5f5f7] font-mono">
                            {idea.symbol}
                        </h3>
                        <span className="text-[10px] bg-[#1d1d1f] text-[#86868b] px-2 py-0.5 rounded-full font-semibold uppercase tracking-wider">{idea.sector}</span>
                        <span
                            className="text-[10px] px-2 py-0.5 rounded-full font-semibold uppercase tracking-wider"
                            style={idea.regime_alignment === 'aligned' ? { background: 'rgba(16, 185, 129, 0.1)', borderColor: 'rgba(16, 185, 129, 0.3)', color: '#10b981', borderWidth: 1 } : { background: 'rgba(148, 163, 184, 0.1)', borderColor: 'rgba(148, 163, 184, 0.3)', color: '#94a3b8', borderWidth: 1 }}
                        >
                            {idea.regime_alignment}
                        </span>
                    </div>
                    <p className="text-[10px] text-[#86868B] font-mono mt-1">
                        Sector rank #{idea.sector_rank} · Expected annual return {formatPct(idea.expected_return_annual)}
                    </p>
                </div>
                <div className="text-right">
                    <div className="text-2xl font-bold font-mono text-[#f5f5f7]">{idea.checklist_score}/10</div>
                    <div className="text-[10px] uppercase tracking-[0.08em] font-bold text-[#86868B]">Checklist score</div>
                </div>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                <div className="rounded-xl border border-[#2d2d2d] bg-[#0a0a0a] px-3 py-2">
                    <div className="text-[10px] uppercase tracking-[0.08em] font-bold text-[#86868B]">Entry</div>
                    <div className="font-semibold text-[#f5f5f7] font-mono">Rs {idea.entry_price.toFixed(2)}</div>
                </div>
                <div className="rounded-xl border border-[#2d2d2d] bg-[#0a0a0a] px-3 py-2">
                    <div className="text-[10px] uppercase tracking-[0.08em] font-bold text-[#86868B]">Stop</div>
                    <div className="font-semibold text-[#f5f5f7] font-mono">Rs {idea.stop_loss.toFixed(2)}</div>
                </div>
                <div className="rounded-xl border border-[#2d2d2d] bg-[#0a0a0a] px-3 py-2">
                    <div className="text-[10px] uppercase tracking-[0.08em] font-bold text-[#86868B]">Target</div>
                    <div className="font-semibold text-[#f5f5f7] font-mono">Rs {idea.target_price.toFixed(2)}</div>
                </div>
                <div className="rounded-xl border border-[#2d2d2d] bg-[#0a0a0a] px-3 py-2">
                    <div className="text-[10px] uppercase tracking-[0.08em] font-bold text-[#86868B]">Risk / Reward</div>
                    <div className="font-semibold text-[#f5f5f7] font-mono">{idea.risk_reward_ratio.toFixed(2)}:1</div>
                </div>
            </div>

            <div className="flex flex-wrap gap-3 text-[10px] font-mono text-[#86868B] mb-4">
                <span className="flex items-center gap-1.5 px-2 py-1 bg-[#1d1d1f] border border-[#2d2d2d] rounded-lg">
                    <Target className="w-3 h-3 text-emerald-500" />
                    Size {idea.suggested_allocation_pct.toFixed(2)}% of portfolio
                </span>
                <span className="flex items-center gap-1.5 px-2 py-1 bg-[#1d1d1f] border border-[#2d2d2d] rounded-lg">
                    <ShieldCheck className="w-3 h-3 text-yellow-500" />
                    Max loss per unit Rs {idea.max_loss_per_unit.toFixed(2)}
                </span>
                {idea.catalyst && (
                    <span className="flex items-center gap-1.5 px-2 py-1 bg-[#1d1d1f] border border-[#2d2d2d] rounded-lg">
                        <TrendingUp className="w-3 h-3 text-yellow-500" />
                        Driver: {idea.catalyst}
                    </span>
                )}
            </div>

            <div className="space-y-2">
                {checklistItems.map(item => (
                    <div key={item.name} className="flex items-start gap-2 text-[10px] font-mono">
                        <span className={`mt-0.5 ${item.check.passed ? 'text-emerald-500' : 'text-amber-500'}`}>
                            {item.check.passed ? '✓' : '⚠'}
                        </span>
                        <div>
                            <div className={`font-semibold ${item.check.passed ? 'text-[#f5f5f7]' : 'text-[#86868B]'}`}>
                                {item.name}
                                <span className="ml-2 text-[10px] text-[#6e6e73]">({Math.round(item.check.score * 100)}%)</span>
                            </div>
                            <div className="text-[10px] leading-relaxed text-[#86868B] mt-0.5">{item.check.reason}</div>
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
            <div className="bg-[#141415] border border-[#2d2d2d] rounded-2xl p-4">
                <div className="flex items-center justify-between gap-4">
                    <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-xl bg-[#0a0a0a] border border-[#2d2d2d] flex items-center justify-center">
                            <Target className="w-4 h-4 text-yellow-500" />
                        </div>
                        <div>
                            <h2 className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em]">Decision Engine</h2>
                            <p className="text-[10px] text-[#86868B] font-mono mt-1">
                                Regime fit, sector strength, technical setup, risk framing, and key news hooks.
                            </p>
                        </div>
                    </div>
                    <button onClick={loadIdeas} disabled={loading} className="bg-[#1d1d1f] border border-[#2d2d2d] rounded-xl font-bold hover:bg-[#2d2d2d] transition-all px-4 py-2 text-[10px] uppercase tracking-[0.08em] flex items-center gap-2 text-[#f5f5f7] disabled:opacity-50">
                        <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
                        Refresh
                    </button>
                </div>
            </div>

            {error && (
                <div className="bg-red-900/20 border border-red-900/50 text-red-200 p-4 rounded-2xl text-sm flex items-start gap-2">
                    <AlertTriangle className="w-4 h-4 mt-0.5 text-red-500" />
                    <span>{error}</span>
                </div>
            )}

            {loading && ideas.length === 0 && (
                <div className="bg-[#141415] border border-[#2d2d2d] rounded-2xl p-5 text-[10px] font-mono text-[#86868B]">Scanning the universe and assembling trade ideas...</div>
            )}

            {!loading && !error && ideas.length === 0 && (
                <div className="bg-[#141415] border border-[#2d2d2d] rounded-2xl p-5 text-[10px] font-mono text-[#86868B]">
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
