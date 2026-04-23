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
      {/* SLEEK DARK MODE TOGGLE HEADER */}
      <div className="bg-[#141415] border border-slate-800/60 rounded-2xl p-4 mb-6 flex flex-col md:flex-row justify-between md:items-center gap-4">
          
          {/* Left Side: Context */}
          <div>
              <h1 className="text-lg font-bold text-slate-100 font-serif tracking-tight">
                  Decision Engine
              </h1>
              <p className="text-[10px] text-slate-500 font-mono mt-1 uppercase tracking-widest">
                  Unified stack for mandate generation and exposure analysis
              </p>
          </div>

          {/* Right Side: The Toggle Switch */}
          <div className="flex bg-[#0a0a0a] border border-slate-800 rounded-xl p-1 shrink-0">
              <button 
                  onClick={() => setView('build')} 
                  className={`px-5 py-2 rounded-lg text-[10px] font-bold uppercase tracking-widest transition-all ${
                      view === 'build' 
                      ? 'bg-[#eab308] text-black shadow-sm' 
                      : 'text-slate-500 hover:text-slate-300'
                  }`}
              >
                  Build Portfolio
              </button>
              <button 
                  onClick={() => setView('analyze')} 
                  className={`px-5 py-2 rounded-lg text-[10px] font-bold uppercase tracking-widest transition-all ${
                      view === 'analyze' 
                      ? 'bg-[#eab308] text-black shadow-sm' 
                      : 'text-slate-500 hover:text-slate-300'
                  }`}
              >
                  Analyze Holdings
              </button>
          </div>

      </div>
      
      {portfolio?.regimeWarning && (
        <div className="bg-rose-500/10 border border-rose-500/30 rounded-2xl p-5 mb-6 relative overflow-hidden">
            <div className="absolute top-0 left-0 w-1 h-full bg-rose-500"></div>
            <h3 className="text-[10px] font-bold text-rose-500 uppercase tracking-[0.15em] flex items-center gap-2 mb-2">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                Bear Market Warning
            </h3>
            <p className="text-[11px] text-rose-400/90 leading-relaxed font-mono italic">
                {portfolio.regimeWarning}
            </p>
        </div>
      )}

      {view === 'build' ? <GenerateTab onPortfolioGenerated={onPortfolioGenerated} portfolio={portfolio} /> : <AnalyzeTab />}
    </div>
  );
}
