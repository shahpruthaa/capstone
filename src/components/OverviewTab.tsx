import React, { useEffect, useState } from 'react';
import { Activity, Brain, Database, RefreshCw, TrendingUp, Zap } from 'lucide-react';
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

import { MetricCard } from './MetricCard';
import {
  CurrentModelStatus,
  getCurrentModelStatusViaApi,
  getMarketDashboardViaApi,
  getMarketDataSummaryViaApi,
  MarketDashboard,
  MarketDataSummary,
} from '../services/backendApi';

function fmtPct(value?: number | null, digits = 2): string {
  if (value === undefined || value === null || Number.isNaN(value)) return '--';
  return `${value.toFixed(digits)}%`;
}

function fmtSignedPct(value?: number | null, digits = 2): string {
  if (value === undefined || value === null || Number.isNaN(value)) return '--';
  return `${value >= 0 ? '+' : ''}${value.toFixed(digits)}%`;
}

function fmtNum(value?: number | null, digits = 2): string {
  if (value === undefined || value === null || Number.isNaN(value)) return '--';
  return value.toFixed(digits);
}

function deriveSentiment(dashboard: MarketDashboard | null): 'Bullish' | 'Neutral' | 'Bearish' {
  if (!dashboard) return 'Neutral';
  if (dashboard.trend.above200Dma && dashboard.trend.breadthAbove50Pct >= 55) return 'Bullish';
  if (!dashboard.trend.above200Dma && dashboard.trend.breadthAbove50Pct < 45) return 'Bearish';
  return 'Neutral';
}

function deriveVolatilityLabel(dashboard: MarketDashboard | null): 'Low' | 'Moderate' | 'High' {
  const vol = dashboard?.trend.realizedVolatilityPct ?? 0;
  if (vol <= 16) return 'Low';
  if (vol <= 24) return 'Moderate';
  return 'High';
}

function formatShortDate(value?: string): string {
  if (!value) return '--';
  return value;
}

export function OverviewTab() {
  const [modelStatus, setModelStatus] = useState<CurrentModelStatus | null>(null);
  const [dashboard, setDashboard] = useState<MarketDashboard | null>(null);
  const [marketData, setMarketData] = useState<MarketDataSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [requestLatencyMs, setRequestLatencyMs] = useState<number | null>(null);

  const load = async () => {
    setLoading(true);
    setError('');
    const startedAt = performance.now();
    try {
      const [currentModel, regimeDashboard, summary] = await Promise.all([
        getCurrentModelStatusViaApi(),
        getMarketDashboardViaApi(),
        getMarketDataSummaryViaApi(),
      ]);
      setModelStatus(currentModel);
      setDashboard(regimeDashboard);
      setMarketData(summary);
      setRequestLatencyMs(performance.now() - startedAt);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load overview data.');
      setRequestLatencyMs(performance.now() - startedAt);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const validation = modelStatus?.validationOverview;
  const factorLeaders = (dashboard?.factorWeather ?? []).slice(0, 3);
  const combinedNotes = [
    ...(modelStatus?.notes ?? []),
    ...(dashboard?.notes ?? []),
    ...(marketData?.notes ?? []),
  ].slice(0, 5);

  return (
    <div className="space-y-5">
      <div className="card p-5" style={{ background: 'linear-gradient(135deg, rgba(255, 93, 162, 0.15), rgba(255, 196, 107, 0.12))' }}>
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Brain className="w-4 h-4 text-sky-700" />
              <h2 className="font-bold text-slate-900">Live Research Overview</h2>
            </div>
            <p className="text-sm text-slate-600 leading-relaxed">
              Overview is now driven by the live model runtime, market-regime dashboard, validation artifact, and local bhavcopy coverage instead of synthetic placeholders.
            </p>
          </div>
          <button onClick={() => void load()} disabled={loading} className="btn-primary px-4 py-2 text-sm flex items-center gap-2">
            <RefreshCw className={`w-4 h-4 ${loading ? 'spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {error && <div className="alert-warning text-sm">{error}</div>}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard
          label="OOS Sharpe"
          value={fmtNum(validation?.oosSharpeRatio)}
          sub={validation?.available ? `Fold count ${validation.foldCount ?? 0}` : 'Validation unavailable'}
          color={validation?.oosSharpeRatio && validation.oosSharpeRatio > 0 ? 'green' : 'red'}
        />
        <MetricCard
          label="Information Coef."
          value={fmtNum(validation?.informationCoefficient, 3)}
          sub={validation?.selectionStatus ?? 'No validation summary'}
          color={validation?.informationCoefficient && validation.informationCoefficient > 0 ? 'green' : 'red'}
        />
        <MetricCard
          label="Hit Rate"
          value={fmtPct(validation?.hitRatePct)}
          sub={validation?.sampleCount ? `${validation.sampleCount} scored rows` : 'No scored rows'}
          color={(validation?.hitRatePct ?? 0) >= 50 ? 'green' : 'amber'}
        />
        <MetricCard
          label="Request Latency"
          value={requestLatencyMs ? `${Math.round(requestLatencyMs)}ms` : '--'}
          sub={marketData?.sessionStatus?.label ?? 'Session state pending'}
          color={requestLatencyMs && requestLatencyMs < 1200 ? 'green' : 'amber'}
        />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
        <div className="card p-5">
          <div className="flex items-center gap-2 mb-4">
            <Activity className="w-4 h-4 text-slate-700" />
            <h3 className="font-bold text-slate-900">Research Status</h3>
          </div>
          <div className="space-y-3">
            <div>
              <div className="progress-bar-track">
                <div className="progress-bar-fill" style={{ width: `${modelStatus?.healthScorePct ?? 0}%` }} />
              </div>
              <p className="text-xs text-slate-500 mt-2">{modelStatus?.healthScorePct ?? 0}% runtime health</p>
            </div>
            <div className="stat-row"><span className="stat-label">Variant</span><span className="stat-value">{modelStatus?.variant ?? '--'}</span></div>
            <div className="stat-row"><span className="stat-label">Mode</span><span className="stat-value">{modelStatus?.trainingMode ?? '--'}</span></div>
            <div className="stat-row"><span className="stat-label">Model Version</span><span className="stat-value">{modelStatus?.modelVersion ?? '--'}</span></div>
            <div className="stat-row"><span className="stat-label">Artifact</span><span className="stat-value">{modelStatus?.artifactClassification ?? '--'}</span></div>
          </div>
        </div>

        <div className="card p-5">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp className="w-4 h-4 text-slate-700" />
            <h3 className="font-bold text-slate-900">Market Regime Pulse</h3>
          </div>
          <div className="space-y-3">
            <div className="stat-row"><span className="stat-label">Sentiment</span><span className="stat-value">{deriveSentiment(dashboard)}</span></div>
            <div className="stat-row"><span className="stat-label">Volatility</span><span className="stat-value">{deriveVolatilityLabel(dashboard)}</span></div>
            <div className="stat-row"><span className="stat-label">Breadth {'>'} 50 DMA</span><span className="stat-value">{fmtPct(dashboard?.trend.breadthAbove50Pct)}</span></div>
            <div className="stat-row"><span className="stat-label">Drawdown State</span><span className="stat-value">{dashboard?.trend.drawdownState ?? '--'}</span></div>
            <div>
              <p className="section-title">Factor Leaders</p>
              <div className="flex flex-wrap gap-2">
                {factorLeaders.map((factor) => (
                  <span key={factor.factor} className="factor-tag">
                    {factor.factor}: {factor.leader}
                  </span>
                ))}
                {!factorLeaders.length && <span className="text-xs text-slate-500">No factor leadership data yet.</span>}
              </div>
            </div>
          </div>
        </div>

        <div className="card p-5">
          <div className="flex items-center gap-2 mb-4">
            <Database className="w-4 h-4 text-slate-700" />
            <h3 className="font-bold text-slate-900">Data Freshness</h3>
          </div>
          <div className="space-y-3">
            <div className="stat-row"><span className="stat-label">Latest Trade Date</span><span className="stat-value">{formatShortDate(marketData?.maxTradeDate)}</span></div>
            <div className="stat-row"><span className="stat-label">Daily Bars</span><span className="stat-value">{marketData?.dailyBarCount ?? 0}</span></div>
            <div className="stat-row"><span className="stat-label">Instruments</span><span className="stat-value">{marketData?.instrumentCount ?? 0}</span></div>
            <div className="stat-row"><span className="stat-label">NSE Session</span><span className="stat-value">{marketData?.sessionStatus?.label ?? '--'}</span></div>
            <p className="text-xs text-slate-500">{marketData?.sessionStatus?.reason ?? 'Waiting for market session context.'}</p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
        <div className="card p-5">
          <div className="flex items-center gap-2 mb-4">
            <Zap className="w-4 h-4 text-slate-700" />
            <h3 className="font-bold text-slate-900">Current Signals</h3>
          </div>
          <div className="space-y-3">
            {(modelStatus?.currentSignals ?? []).map((signal) => (
              <div key={signal.symbol} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-slate-900">{signal.symbol}</p>
                    <p className="text-[11px] text-slate-500">{signal.sector}</p>
                  </div>
                  <div className="text-right">
                    <p className={`text-sm font-semibold ${signal.action === 'BUY' ? 'text-emerald-600' : signal.action === 'SELL' ? 'text-rose-500' : 'text-amber-600'}`}>
                      {signal.action}
                    </p>
                    <p className="text-[11px] text-slate-500">{Math.round(signal.confidence * 100)}% confidence</p>
                  </div>
                </div>
                <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                  <span>21D {fmtSignedPct(signal.predictedReturn21dPct)}</span>
                  <span>Annual {fmtSignedPct(signal.predictedAnnualReturnPct)}</span>
                </div>
                {!!signal.topDrivers.length && (
                  <p className="text-[11px] text-slate-500 mt-2">{signal.topDrivers.join(' | ')}</p>
                )}
              </div>
            ))}
            {!modelStatus?.currentSignals?.length && <p className="text-sm text-slate-500">No live signals are available yet.</p>}
          </div>
        </div>

        <div className="card p-5">
          <p className="section-title">Walk-forward Equity Curve</p>
          <div className="h-72">
            {validation?.walkForwardEquityCurve?.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={validation.walkForwardEquityCurve}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                  <XAxis dataKey="date" fontSize={10} tickFormatter={(value) => String(value).slice(2, 7)} />
                  <YAxis fontSize={10} domain={['auto', 'auto']} />
                  <Tooltip
                    formatter={(value: number, name: string) => [name.includes('Pct') ? `${value.toFixed(2)}%` : value.toFixed(2), name]}
                    labelFormatter={(label) => `Decision date: ${label}`}
                  />
                  <Line type="monotone" dataKey="equityIndex" name="Equity Index" stroke="#ff5da2" strokeWidth={2.5} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full grid place-items-center text-sm text-slate-500">
                No walk-forward equity curve is available for the current artifact.
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="card p-5">
        <p className="section-title">Runtime Notes</p>
        <div className="space-y-2">
          {combinedNotes.length ? combinedNotes.map((note, index) => (
            <p key={index} className="text-sm text-slate-600">{note}</p>
          )) : <p className="text-sm text-slate-500">No runtime notes are available.</p>}
        </div>
      </div>
    </div>
  );
}
