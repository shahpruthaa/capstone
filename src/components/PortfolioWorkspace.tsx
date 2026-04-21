import React, { useState, useEffect } from 'react';

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

  useEffect(() => {
    if (window.pendingAiAction === 'analyze_portfolio') {
      setView('analyze');
      window.pendingAiAction = undefined;
    }

    const handleAction = (e: any) => {
      if (e.detail.name === 'analyze_portfolio') {
        setView('analyze');
      } else if (e.detail.name === 'generate_portfolio') {
        setView('build');
      }
    };
    window.addEventListener('AI_ACTION', handleAction);
    return () => window.removeEventListener('AI_ACTION', handleAction);
  }, []);

  return (
    <div className="space-y-6">
      <div className="card p-5">
        <p className="section-title">Portfolio Workflow</p>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-xl font-bold text-slate-50">Build or analyze with the same decision engine</h2>
            <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-400">
              Step 1: define the mandate. Step 2: review the recommended portfolio. Step 3: compare it against your real holdings using the same research stack.
            </p>
          </div>
          <div className="flex gap-2 rounded-2xl border border-slate-700/60 bg-slate-950/40 p-1">
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

      {view === 'build' ? (
        <GenerateTab onPortfolioGenerated={onPortfolioGenerated} portfolio={portfolio} />
      ) : (
        <AnalyzeTab />
      )}
    </div>
  );
}
