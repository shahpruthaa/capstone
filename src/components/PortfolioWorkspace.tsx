import React, { useState } from 'react';

import { AnalyzeTab } from './AnalyzeTab';
import { GenerateTab } from './GenerateTab';
import { Portfolio } from '../services/portfolioService';

type WorkspaceView = 'build' | 'analyze';

interface Props {
  onPortfolioGenerated: (portfolio: Portfolio) => void;
  portfolio: Portfolio | null;
}

export function PortfolioWorkspace({ onPortfolioGenerated, portfolio }: Props) {
  const [view, setView] = useState<WorkspaceView>('build');

  return (
    <div className="space-y-6">
      <div className="card p-4">
        <p className="section-title">Portfolio Workflow</p>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-xl font-bold text-slate-50">Build or analyze with the same decision engine</h2>
            <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-600">
              Step 1: define the mandate. Step 2: review the recommended portfolio. Step 3: compare it against your real holdings using the same research stack.
            </p>
          </div>
          <div className="flex gap-2 rounded-sm border border-slate-700 bg-slate-800/50 p-1">
            <button
              className={`${view === 'build' ? 'btn-primary' : 'btn-secondary'} px-4 py-2 text-sm`}
              onClick={() => setView('build')}
            >
              Build Portfolio
            </button>
            <button
              className={`${view === 'analyze' ? 'btn-primary' : 'btn-secondary'} px-4 py-2 text-sm`}
              onClick={() => setView('analyze')}
            >
              Analyze Holdings
            </button>
          </div>
        </div>
      </div>
      
      {portfolio?.regimeWarning && (
        <div className="rounded-sm border border-amber-500/30 bg-amber-500/10 p-4">
          <div className="flex gap-3">
            <div className="text-amber-500">
              <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <div>
              <h3 className="font-medium text-amber-500">Bear Market Warning</h3>
              <p className="mt-1 text-sm text-amber-200/80">
                {portfolio.regimeWarning}
              </p>
            </div>
          </div>
        </div>
      )}

      {view === 'build' ? <GenerateTab onPortfolioGenerated={onPortfolioGenerated} portfolio={portfolio} /> : <AnalyzeTab />}
    </div>
  );
}
