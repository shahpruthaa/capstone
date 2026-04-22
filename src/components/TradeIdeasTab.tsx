import React, { useEffect, useState } from 'react';
import { AlertTriangle, RefreshCw, Target, TrendingUp } from 'lucide-react';

import { fetchTradeIdeasViaApi, TradeIdea, TradeIdeasResponse } from '../services/backendApi';
import { Portfolio } from '../services/portfolioService';
import { PortfolioFitBanner } from './PortfolioFitBanner';

function formatPct(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function qualityBadge(kind?: 'live' | 'proxy' | 'placeholder') {
  if (kind === 'live') return 'badge-green';
  if (kind === 'proxy') return 'badge-amber';
  return 'badge-neutral';
}

function TradeIdeaCard({ idea }: { idea: TradeIdea }) {
  const checklistItems = [
    { name: 'Regime aligned', check: idea.checklist.regime_check },
    { name: 'Sector strength', check: idea.checklist.sector_strength },
    { name: 'Relative strength', check: idea.checklist.relative_strength },
    { name: 'Technical setup', check: idea.checklist.technical_setup },
    { name: 'Options context', check: idea.checklist.options_positioning },
    { name: 'Flow proxy', check: idea.checklist.fii_dii_flow },
    { name: 'Fundamental proxy', check: idea.checklist.fundamental_health },
    { name: 'Catalyst', check: idea.checklist.news_catalyst },
    { name: 'Entry / stop / target', check: idea.checklist.entry_stop_target },
    { name: 'Sizing', check: idea.checklist.position_sizing },
  ];

  return (
    <div className="card p-5">
      <div className="flex items-start justify-between gap-4 mb-3">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="font-bold text-lg text-slate-900">{idea.symbol}</h3>
            <span className="badge badge-neutral">{idea.sector}</span>
            <span className="badge badge-neutral">{idea.regime_alignment}</span>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Sector rank #{idea.sector_rank} | Expected annual return {formatPct(idea.expected_return_annual)} | Expected hold {idea.expected_holding_period_days}D
          </p>
        </div>
        <div className="text-right">
          <div className="text-2xl font-bold text-slate-900">{idea.checklist_score}/10</div>
          <div className="text-xs text-slate-500">Checklist score</div>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
        <div className="rounded-xl border border-slate-100 bg-slate-50 px-3 py-2">
          <div className="text-[11px] uppercase tracking-wide text-slate-400">Entry</div>
          <div className="font-semibold text-slate-900">Rs {idea.entry_price.toFixed(2)}</div>
        </div>
        <div className="rounded-xl border border-slate-100 bg-slate-50 px-3 py-2">
          <div className="text-[11px] uppercase tracking-wide text-slate-400">Suggested Size</div>
          <div className="font-semibold text-slate-900">{idea.suggested_allocation_pct.toFixed(2)}%</div>
          <div className="text-[11px] text-slate-500">Rs {idea.suggested_allocation_value.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</div>
        </div>
        <div className="rounded-xl border border-slate-100 bg-slate-50 px-3 py-2">
          <div className="text-[11px] uppercase tracking-wide text-slate-400">Units</div>
          <div className="font-semibold text-slate-900">{idea.suggested_units}</div>
          <div className="text-[11px] text-slate-500">Cash-aware sizing</div>
        </div>
        <div className="rounded-xl border border-slate-100 bg-slate-50 px-3 py-2">
          <div className="text-[11px] uppercase tracking-wide text-slate-400">Liquidity</div>
          <div className="font-semibold text-slate-900">{idea.liquidity_slippage_bps.toFixed(1)} bps</div>
          <div className="text-[11px] text-slate-500">{idea.liquidity_commentary}</div>
        </div>
        <div className="rounded-xl border border-slate-100 bg-slate-50 px-3 py-2">
          <div className="text-[11px] uppercase tracking-wide text-slate-400">Marginal Risk</div>
          <div className="font-semibold text-slate-900">{idea.marginal_risk_contribution_pct.toFixed(1)}%</div>
          <div className="text-[11px] text-slate-500">Portfolio contribution</div>
        </div>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 mb-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-2">Portfolio Fit</p>
        <p className="text-sm text-slate-700 leading-relaxed">{idea.portfolio_fit_summary}</p>
        {(idea.overlap_with_holdings.length > 0 || idea.duplicate_factor_bets.length > 0 || idea.hedge_factor_bets.length > 0) && (
          <div className="mt-3 flex flex-wrap gap-2">
            {idea.overlap_with_holdings.map((item) => (
              <span key={item} className="badge badge-neutral">Overlap: {item}</span>
            ))}
            {idea.duplicate_factor_bets.map((item) => (
              <span key={item} className="badge badge-neutral">Duplicate: {item}</span>
            ))}
            {idea.hedge_factor_bets.map((item) => (
              <span key={item} className="badge badge-green">Hedge: {item}</span>
            ))}
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        <div className="space-y-2">
          {checklistItems.map((item) => (
            <div key={item.name} className="flex items-start gap-2 text-sm">
              <span className={`mt-0.5 ${item.check.passed ? 'text-emerald-600' : 'text-amber-500'}`}>{item.check.passed ? 'OK' : 'Watch'}</span>
              <div>
                <div className="font-medium text-slate-800">
                  {item.name}
                  <span className="ml-2 text-xs text-slate-400">({Math.round(item.check.score * 100)}%)</span>
                  <span className={`ml-2 badge ${qualityBadge(item.check.dataQuality)}`}>{item.check.dataQuality || 'live'}</span>
                </div>
                <div className="text-xs leading-relaxed text-slate-500">{item.check.reason}</div>
              </div>
            </div>
          ))}
        </div>

        <div className="space-y-3">
          <div className="rounded-2xl border border-slate-200 bg-white p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-2">Event Calendar</p>
            <div className="space-y-2">
              {idea.event_calendar.map((item) => (
                <p key={item} className="text-sm text-slate-600">{item}</p>
              ))}
            </div>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-2">Execution</p>
            <p className="text-sm text-slate-600">Stop Rs {idea.stop_loss.toFixed(2)} | Target Rs {idea.target_price.toFixed(2)} | R/R {idea.risk_reward_ratio.toFixed(2)}:1</p>
            <p className="text-sm text-slate-600 mt-2">Max loss per unit Rs {idea.max_loss_per_unit.toFixed(2)}</p>
            {idea.catalyst && (
              <p className="text-sm text-slate-600 mt-2 flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-blue-600" />
                {idea.catalyst}
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export function TradeIdeasTab({ portfolio }: { portfolio: Portfolio | null }) {
  const [response, setResponse] = useState<TradeIdeasResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadIdeas = async () => {
    setLoading(true);
    setError('');
    try {
      setResponse(await fetchTradeIdeasViaApi({ regimeAware: true, minChecklistScore: 7, maxIdeas: 8, portfolio }));
    } catch (err) {
      setResponse(null);
      setError(err instanceof Error ? err.message : 'Unable to load trade ideas right now.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadIdeas();
  }, [portfolio]);

  return (
    <div className="space-y-5">
      <div className="card p-5" style={{ background: 'linear-gradient(135deg, rgba(8, 145, 178, 0.18), rgba(15, 23, 42, 0.22))' }}>
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Target className="w-4 h-4 text-cyan-700" />
              <h2 className="font-bold text-slate-900">Trade Ideas With Portfolio Context</h2>
            </div>
            <p className="text-sm text-slate-600 leading-relaxed">
              Ideas are now sized off live portfolio value, cash, and sector exposure, and each card explains whether it adds concentration,
              duplicates a factor bet, or helps hedge the current book.
            </p>
          </div>
          <button onClick={() => void loadIdeas()} disabled={loading} className="btn-primary px-4 py-2 text-sm flex items-center gap-2">
            <RefreshCw className={`w-4 h-4 ${loading ? 'spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      <PortfolioFitBanner summary={response?.portfolioFitSummary || portfolio?.portfolioFitSummary} />

      {response?.notes?.length ? (
        <div className="card p-4">
          {response.notes.map((note, index) => (
            <p key={index} className="text-xs text-slate-500">{note}</p>
          ))}
        </div>
      ) : null}

      {error && (
        <div className="alert-warning text-sm flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      {loading && !response && <div className="card p-5 text-sm text-slate-500">Scanning the universe and fitting ideas to the live portfolio...</div>}

      {!loading && !error && (response?.ideas.length ?? 0) === 0 && (
        <div className="card p-5 text-sm text-slate-500">
          No ideas cleared the current 7/10 threshold with the supplied portfolio constraints.
        </div>
      )}

      <div className="space-y-4">
        {(response?.ideas ?? []).map((idea) => (
          <TradeIdeaCard key={idea.symbol} idea={idea} />
        ))}
      </div>
    </div>
  );
}
