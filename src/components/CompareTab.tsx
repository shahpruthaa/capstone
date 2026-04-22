import React, { useEffect, useMemo, useState } from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  BarChart,
  Bar,
} from 'recharts';
import { GitCompare, RefreshCw } from 'lucide-react';

import { BenchmarkCompareResponse, getBenchmarkCompareViaApi } from '../services/backendApi';
import { Portfolio } from '../services/portfolioService';
import { MetricCard } from './MetricCard';
import { PortfolioFitBanner } from './PortfolioFitBanner';

function fmtPct(value: number): string {
  return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
}

export function CompareTab({ portfolio }: { portfolio: Portfolio | null }) {
  const [compare, setCompare] = useState<BenchmarkCompareResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState('');

  const load = async () => {
    setLoading(true);
    setNotice('');
    try {
      const response = await getBenchmarkCompareViaApi(portfolio);
      setCompare(response);
      setNotice('Compare is using the current mandate or generated book instead of the old fixed house portfolio.');
    } catch (error) {
      setCompare(null);
      setNotice(error instanceof Error ? error.message : 'Compare service is unavailable.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [portfolio]);

  const leadStrategy = compare?.strategies[0];
  const rollingExcessData = useMemo(
    () =>
      (compare?.series ?? []).map((point) => ({
        date: point.date,
        ...point.rollingExcessReturn,
      })),
    [compare],
  );
  const rollingSharpeData = useMemo(
    () =>
      (compare?.series ?? []).map((point) => ({
        date: point.date,
        ...point.rollingSharpe,
      })),
    [compare],
  );
  const compareBars = useMemo(
    () =>
      (compare?.strategies ?? []).map((strategy) => ({
        name: strategy.strategyName.slice(0, 18),
        TrackingError: strategy.trackingErrorPct,
        InfoRatio: strategy.informationRatio,
        ActiveShare: strategy.activeSharePct,
      })),
    [compare],
  );

  if (!compare && loading) {
    return <div className="card p-5 text-sm text-slate-500">Loading matched benchmark comparison...</div>;
  }

  return (
    <div className="space-y-5 animate-fade-in">
      <div className="card p-6" style={{ background: 'linear-gradient(135deg, rgba(14, 116, 144, 0.16), rgba(15, 23, 42, 0.16))' }}>
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <GitCompare className="w-4 h-4 text-cyan-700" />
              <h2 className="font-bold text-slate-900">Mandate-Aware Benchmark Compare</h2>
            </div>
            <p className="text-sm text-slate-600 leading-relaxed">
              Compare now matches benchmarks to the current book’s breadth and risk target, then measures active share,
              tracking error, information ratio, capture ratios, and net-of-cost/net-of-tax outcomes on one footing.
            </p>
            {compare?.benchmarkMatchSummary && <p className="mt-3 text-xs text-slate-500">{compare.benchmarkMatchSummary}</p>}
            {notice && <p className="mt-2 text-xs text-slate-500">{notice}</p>}
          </div>
          <button onClick={() => void load()} disabled={loading} className="btn-primary px-4 py-2 text-sm flex items-center gap-2">
            <RefreshCw className={`w-4 h-4 ${loading ? 'spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      <PortfolioFitBanner summary={compare?.portfolioFitSummary} />

      {leadStrategy && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <MetricCard label="Active Share" value={`${leadStrategy.activeSharePct.toFixed(1)}%`} sub={leadStrategy.benchmarkName} color="blue" />
          <MetricCard label="Tracking Error" value={`${leadStrategy.trackingErrorPct.toFixed(2)}%`} sub="annualized" color="amber" />
          <MetricCard label="Info Ratio" value={leadStrategy.informationRatio.toFixed(2)} sub="active return / TE" color={leadStrategy.informationRatio >= 0 ? 'green' : 'red'} />
          <MetricCard label="Downside Capture" value={`${leadStrategy.downsideCapturePct.toFixed(0)}%`} sub="vs matched benchmark" color={leadStrategy.downsideCapturePct <= 100 ? 'green' : 'red'} />
          <MetricCard label="Net Alpha" value={fmtPct(leadStrategy.exAnteAlphaPct)} sub="ex-ante vs matched benchmark" color={leadStrategy.exAnteAlphaPct >= 0 ? 'green' : 'red'} />
        </div>
      )}

      {compare && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
          <div className="card p-5">
            <p className="section-title">Rolling Excess Return</p>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={rollingExcessData}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="date" fontSize={10} tickFormatter={(value) => value.slice(5)} />
                  <YAxis fontSize={10} unit="%" />
                  <Tooltip />
                  <Legend />
                  {compare.strategies.map((strategy, index) => (
                    <Line
                      key={strategy.strategyName}
                      type="monotone"
                      dataKey={strategy.strategyName}
                      stroke={['#14b8a6', '#3b82f6', '#f59e0b'][index % 3]}
                      strokeWidth={index === 0 ? 2.5 : 1.75}
                      dot={false}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="card p-5">
            <p className="section-title">Rolling Sharpe</p>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={rollingSharpeData}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="date" fontSize={10} tickFormatter={(value) => value.slice(5)} />
                  <YAxis fontSize={10} />
                  <Tooltip />
                  <Legend />
                  {compare.strategies.map((strategy, index) => (
                    <Line
                      key={strategy.strategyName}
                      type="monotone"
                      dataKey={strategy.strategyName}
                      stroke={['#0f766e', '#475569', '#ea580c'][index % 3]}
                      strokeWidth={index === 0 ? 2.5 : 1.75}
                      dot={false}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}

      {compare && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
          <div className="card p-5">
            <p className="section-title">Active Risk Snapshot</p>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={compareBars}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="name" fontSize={10} interval={0} angle={-18} textAnchor="end" height={52} />
                  <YAxis fontSize={10} />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="TrackingError" fill="#f59e0b" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="InfoRatio" fill="#14b8a6" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="ActiveShare" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="card p-5">
            <p className="section-title">Comparison Notes</p>
            <div className="space-y-2">
              {compare.notes.map((note, index) => (
                <p key={index} className="text-sm text-slate-600 leading-relaxed">
                  {note}
                </p>
              ))}
            </div>
          </div>
        </div>
      )}

      {compare && (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Strategy</th>
                  <th>Annual Ret%</th>
                  <th>Vol%</th>
                  <th>Sharpe</th>
                  <th>TE%</th>
                  <th>IR</th>
                  <th>Up/Down Capture</th>
                  <th>DD Duration</th>
                  <th>Recovery</th>
                  <th>Net Cost%</th>
                  <th>Net Tax%</th>
                </tr>
              </thead>
              <tbody>
                {compare.strategies.map((strategy, index) => (
                  <tr key={strategy.strategyName} className={index === 0 ? 'bg-cyan-50' : ''}>
                    <td>
                      <div className="font-semibold text-slate-900">{strategy.strategyName}</div>
                      <div className="text-[11px] text-slate-500">{strategy.matchedOn}</div>
                    </td>
                    <td className="font-mono">{strategy.annualReturnPct.toFixed(2)}%</td>
                    <td className="font-mono">{strategy.volatilityPct.toFixed(2)}%</td>
                    <td className="font-mono">{strategy.sharpeRatio.toFixed(2)}</td>
                    <td className="font-mono">{strategy.trackingErrorPct.toFixed(2)}%</td>
                    <td className="font-mono">{strategy.informationRatio.toFixed(2)}</td>
                    <td className="font-mono">
                      {strategy.upsideCapturePct.toFixed(0)} / {strategy.downsideCapturePct.toFixed(0)}
                    </td>
                    <td className="font-mono">{strategy.drawdownDurationDays}d</td>
                    <td className="font-mono">{strategy.recoveryDays}d</td>
                    <td className="font-mono">{strategy.netOfCostReturnPct.toFixed(2)}%</td>
                    <td className="font-mono">{strategy.netOfTaxReturnPct.toFixed(2)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
