import React from 'react';

import { PortfolioFitSummary } from '../services/analyticsSchema';

export function PortfolioFitBanner({
  title = 'Portfolio Fit',
  summary,
}: {
  title?: string;
  summary: PortfolioFitSummary | null | undefined;
}) {
  return (
    <div className="card p-5">
      <p className="section-title">{title}</p>
      <p className="text-sm text-slate-700 leading-relaxed">
        {summary?.summary || 'Risk level, diversification, concentration, and next action will populate once enough portfolio context is available.'}
      </p>
      {summary && (
        <div className="mt-4 grid grid-cols-1 md:grid-cols-4 gap-3">
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
            <p className="text-[11px] uppercase tracking-wide text-slate-400 font-semibold mb-1">Risk</p>
            <p className="text-sm font-semibold text-slate-900">{summary.riskLevel}</p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
            <p className="text-[11px] uppercase tracking-wide text-slate-400 font-semibold mb-1">Diversification</p>
            <p className="text-sm font-semibold text-slate-900">{summary.diversification}</p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
            <p className="text-[11px] uppercase tracking-wide text-slate-400 font-semibold mb-1">Concentration</p>
            <p className="text-sm font-semibold text-slate-900">{summary.concentration}</p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
            <p className="text-[11px] uppercase tracking-wide text-slate-400 font-semibold mb-1">Next Action</p>
            <p className="text-sm font-semibold text-slate-900">{summary.nextAction}</p>
          </div>
        </div>
      )}
    </div>
  );
}
