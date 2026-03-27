import React, { Suspense, lazy, useEffect, useState } from 'react';
import './index.css';
import { TrendingUp, BarChart2, PieChart, GitCompare, Activity } from 'lucide-react';
import { Portfolio } from './services/portfolioService';
import { AIChat } from './components/AIChat';
import { CurrentModelStatus, getCurrentModelStatusViaApi, getMarketDataSummaryViaApi, MarketDataSummary } from './services/backendApi';

const GenerateTab = lazy(() => import('./components/GenerateTab').then(module => ({ default: module.GenerateTab })));
const AnalyzeTab = lazy(() => import('./components/AnalyzeTab').then(module => ({ default: module.AnalyzeTab })));
const BacktestTab = lazy(() => import('./components/BacktestTab').then(module => ({ default: module.BacktestTab })));
const CompareTab = lazy(() => import('./components/CompareTab').then(module => ({ default: module.CompareTab })));

type Tab = 'GENERATE' | 'ANALYZE' | 'BACKTEST' | 'COMPARE';

const TABS: { id: Tab; label: string; icon: React.ReactNode }[] = [
  { id: 'GENERATE', label: 'Generate', icon: <PieChart className="w-4 h-4" /> },
  { id: 'ANALYZE', label: 'Analyze', icon: <Activity className="w-4 h-4" /> },
  { id: 'BACKTEST', label: 'Backtest', icon: <BarChart2 className="w-4 h-4" /> },
  { id: 'COMPARE', label: 'Compare', icon: <GitCompare className="w-4 h-4" /> },
];

function TabFallback() {
  return (
    <div className="card p-8 text-sm text-slate-500 animate-fade-in">
      Loading portfolio workspace...
    </div>
  );
}

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>('GENERATE');
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [modelStatus, setModelStatus] = useState<CurrentModelStatus | null>(null);
  const [marketData, setMarketData] = useState<MarketDataSummary | null>(null);

  useEffect(() => {
    let active = true;
    Promise.allSettled([getCurrentModelStatusViaApi(), getMarketDataSummaryViaApi()]).then((results) => {
      if (!active) return;
      const [modelResult, marketResult] = results;
      if (modelResult.status === 'fulfilled') setModelStatus(modelResult.value);
      if (marketResult.status === 'fulfilled') setMarketData(marketResult.value);
    });
    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="min-h-screen" style={{ background: 'var(--surface-1)' }}>
      <header
        className="glass sticky top-0 z-40 border-b"
        style={{ borderColor: 'var(--surface-3)' }}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 flex-shrink-0">
            <div
              className="w-9 h-9 rounded-xl flex items-center justify-center"
              style={{ background: 'linear-gradient(135deg, #14b8a6, #0f766e)' }}
            >
              <TrendingUp className="text-white w-5 h-5" />
            </div>
            <div>
              <h1 className="text-base font-bold leading-none" style={{ color: 'var(--text-primary)' }}>
                NSE AI Portfolio
              </h1>
              <p className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
                Local Quant Engine &amp; Portfolio Analytics
              </p>
            </div>
          </div>

          <nav
            className="flex gap-1 p-1 rounded-xl"
            style={{ background: 'var(--surface-2)' }}
          >
            {TABS.map(t => (
              <button
                key={t.id}
                onClick={() => setActiveTab(t.id)}
                className={`nav-tab flex items-center gap-1.5 ${activeTab === t.id ? 'active' : ''}`}
              >
                {t.icon}
                <span className="hidden sm:inline">{t.label}</span>
              </button>
            ))}
          </nav>

          <div className="flex-shrink-0 hidden md:block">
            {portfolio ? (
              <span className="badge badge-green">
                Rs {(portfolio.totalInvested / 100000).toFixed(1)}L · {portfolio.riskProfile.replace('_', ' ')}
              </span>
            ) : (
              <span className="badge badge-slate">No Portfolio</span>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-7 pb-24">
        <div className="card p-4 mb-5">
          <div className="flex flex-wrap gap-3 text-xs">
            <span className={marketData?.available ? 'badge badge-green' : 'badge badge-amber'}>
              Market Data: {marketData?.available ? 'Loaded' : 'Missing'}
            </span>
            <span className={modelStatus?.available ? 'badge badge-green' : 'badge badge-slate'}>
              Model: {modelStatus?.available ? `${modelStatus.variant}${modelStatus.modelVersion ? ` ${modelStatus.modelVersion}` : ''}` : 'Rules fallback'}
            </span>
            <span className="badge badge-slate">
              Training: {modelStatus?.available ? modelStatus.trainingMode || 'unknown' : 'n/a'}
            </span>
            <span className="badge badge-slate">
              Artifact: {modelStatus?.available ? modelStatus.artifactClassification || 'n/a' : 'n/a'}
            </span>
            <span className="badge badge-slate">
              Data Range: {marketData?.minTradeDate && marketData?.maxTradeDate ? `${marketData.minTradeDate} to ${marketData.maxTradeDate}` : 'Unavailable'}
            </span>
            <span className="badge badge-amber">
              Benchmarks: Proxy-aware local research mode
            </span>
          </div>
          {(marketData?.notes?.length || (!modelStatus?.available && modelStatus?.reason)) ? (
            <div className="mt-3 space-y-2">
              {modelStatus?.available === false && modelStatus.reason && (
                <div className="alert-warning text-xs">Model fallback reason: {modelStatus.reason}</div>
              )}
              {marketData?.notes?.slice(0, 2).map((note) => (
                <div key={note} className="alert-info text-xs">{note}</div>
              ))}
            </div>
          ) : null}
        </div>
        <Suspense fallback={<TabFallback />}>
          {activeTab === 'GENERATE' && (
            <GenerateTab
              portfolio={portfolio}
              onPortfolioGenerated={setPortfolio}
            />
          )}
          {activeTab === 'ANALYZE' && <AnalyzeTab />}
          {activeTab === 'BACKTEST' && <BacktestTab portfolio={portfolio} />}
          {activeTab === 'COMPARE' && <CompareTab />}
        </Suspense>
      </main>

      <footer
        className="border-t py-6 mt-4"
        style={{ background: 'var(--surface-0)', borderColor: 'var(--surface-3)' }}
      >
        <div className="max-w-7xl mx-auto px-4 text-center">
          <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
            Disclaimer: This tool is for educational and research use only. It relies on locally ingested NSE market data plus rule-based and LightGBM portfolio models.
            Stock market investments are subject to market risk. Consult a SEBI-registered advisor before investing.
          </p>
          <p className="text-[10px] mt-1" style={{ color: 'var(--text-muted)', opacity: 0.6 }}>
            NSE AI Portfolio Manager · Local FastAPI + TimescaleDB + LightGBM stack · Delivery-equity tax assumptions currently include STCG 20%, LTCG 12.5%, and STT 0.1%.
          </p>
        </div>
      </footer>

      <AIChat portfolio={portfolio} />
    </div>
  );
}
