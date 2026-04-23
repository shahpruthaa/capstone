import React, { useEffect, useState } from 'react';
import { AlertTriangle, Globe2, Newspaper, RefreshCw } from 'lucide-react';

import {
  getMarketContextViaApi,
  getMarketDashboardViaApi,
  getMarketDataSummaryViaApi,
  MarketContext,
  MarketDashboard,
  MarketDataSummary,
} from '../services/backendApi';
import { MetricCard } from './MetricCard';
import { PortfolioFitBanner } from './PortfolioFitBanner';

function formatSigned(value: number, suffix = ''): string {
  return `${value >= 0 ? '+' : ''}${value.toFixed(2)}${suffix}`;
}

export function MarketTab() {
  const [marketData, setMarketData] = useState<MarketDataSummary | null>(null);
  const [marketContext, setMarketContext] = useState<MarketContext | null>(null);
  const [dashboard, setDashboard] = useState<MarketDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const [summary, context, regimeDashboard] = await Promise.all([
        getMarketDataSummaryViaApi(),
        getMarketContextViaApi(),
        getMarketDashboardViaApi(),
      ]);
      setMarketData(summary);
      setMarketContext(context);
      setDashboard(regimeDashboard);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load market context.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  return (
    <div className="space-y-5">
      <div className="card p-5" style={{ background: 'linear-gradient(135deg, rgba(20, 83, 45, 0.22), rgba(8, 47, 73, 0.16))' }}>
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Globe2 className="w-4 h-4 text-sky-700" />
              <h2 className="font-bold text-slate-900">Market Regime and Leadership</h2>
            </div>
            <p className="text-sm text-slate-600 leading-relaxed">
              The market view now combines trend, breadth, realized volatility, drawdown state, factor weather,
              cross-asset tone proxies, and sector relative strength, with clear proxy labels where the direct feed is not live yet.
            </p>
          </div>
          <button onClick={() => void load()} disabled={loading} className="btn-primary px-4 py-2 text-sm flex items-center gap-2">
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

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard label="Index vs 50 DMA" value={dashboard ? (dashboard.trend.above50Dma ? 'Above' : 'Below') : '--'} sub={dashboard ? `${dashboard.trend.indexSymbol} ${dashboard.trend.spot.toFixed(2)}` : 'Loading'} color={dashboard?.trend.above50Dma ? 'green' : 'red'} />
        <MetricCard label="Index vs 200 DMA" value={dashboard ? (dashboard.trend.above200Dma ? 'Above' : 'Below') : '--'} sub={dashboard ? `${dashboard.trend.dma200.toFixed(2)} DMA` : 'Loading'} color={dashboard?.trend.above200Dma ? 'green' : 'red'} />
        <MetricCard label="Breadth > 50 DMA" value={dashboard ? `${dashboard.trend.breadthAbove50Pct.toFixed(0)}%` : '--'} sub={dashboard ? `${dashboard.trend.breadthAbove200Pct.toFixed(0)}% above 200 DMA` : 'Loading'} color="blue" />
        <MetricCard label="Realized Vol" value={dashboard ? `${dashboard.trend.realizedVolatilityPct.toFixed(1)}%` : '--'} sub={dashboard?.trend.drawdownState || 'Loading'} color={dashboard && dashboard.trend.realizedVolatilityPct <= 18 ? 'green' : 'amber'} />
      </div>

      <PortfolioFitBanner title="What This Means For Portfolios Now" summary={dashboard?.whatThisMeansNow} />

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
        <div className="card p-5">
          <p className="section-title">Price-Based Regime</p>
          {dashboard ? (
            <div className="space-y-3 text-sm text-slate-700">
              <div className="stat-row"><span className="stat-label">Spot</span><span className="stat-value">{dashboard.trend.spot.toFixed(2)}</span></div>
              <div className="stat-row"><span className="stat-label">50 DMA</span><span className="stat-value">{dashboard.trend.dma50.toFixed(2)}</span></div>
              <div className="stat-row"><span className="stat-label">200 DMA</span><span className="stat-value">{dashboard.trend.dma200.toFixed(2)}</span></div>
              <div className="stat-row"><span className="stat-label">Breadth above 50</span><span className="stat-value">{dashboard.trend.breadthAbove50Pct.toFixed(1)}%</span></div>
              <div className="stat-row"><span className="stat-label">Breadth above 200</span><span className="stat-value">{dashboard.trend.breadthAbove200Pct.toFixed(1)}%</span></div>
              <div className="stat-row"><span className="stat-label">Drawdown</span><span className="stat-value">{dashboard.trend.drawdownPct.toFixed(1)}%</span></div>
            </div>
          ) : (
            <p className="text-sm text-slate-500">Loading market regime...</p>
          )}
        </div>

        <div className="card p-5">
          <p className="section-title">Factor Weather</p>
          <div className="space-y-3">
            {(dashboard?.factorWeather ?? []).map((item) => (
              <div key={item.factor} className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-slate-900">{item.factor}</p>
                    <p className="text-[11px] text-slate-500">{item.note}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-semibold text-slate-900">{formatSigned(item.leadershipScore)}</p>
                    <p className="text-[11px] text-slate-500">{item.leader}</p>
                  </div>
                </div>
                <div className="mt-2 text-[11px] text-slate-400 uppercase tracking-wide">{item.dataQuality}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="card p-5">
          <p className="section-title">Cross-Asset Tone</p>
          <div className="space-y-3">
            {(dashboard?.crossAssetTone ?? []).map((item) => (
              <div key={item.asset} className="rounded-2xl border border-slate-200 bg-white p-3">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-slate-900">{item.asset}</p>
                    <p className="text-[11px] text-slate-500">{item.note}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-semibold text-slate-900">{item.tone}</p>
                    <div className="flex items-center justify-end gap-1.5">
                      <p className="text-[11px] text-slate-500">{formatSigned(item.movePct, '%')}</p>
                      {item.dataQuality === 'proxy' && (
                        <span className="badge badge-neutral text-[10px] px-1.5 py-0.5">proxy</span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="card p-5">
        <p className="section-title">Sector Relative Strength</p>
        <div className="overflow-x-auto">
          <table className="data-table">
            <thead>
              <tr>
                <th>Sector</th>
                <th>1M</th>
                <th>3M</th>
                <th>6M</th>
                <th>Earnings Revision Trend</th>
                <th>Note</th>
              </tr>
            </thead>
            <tbody>
              {(dashboard?.sectorRelativeStrength ?? []).map((item) => (
                <tr key={item.sector}>
                  <td className="font-semibold text-slate-900">{item.sector}</td>
                  <td className="font-mono">{item.return1mPct.toFixed(2)}%</td>
                  <td className="font-mono">{item.return3mPct.toFixed(2)}%</td>
                  <td className="font-mono">{item.return6mPct.toFixed(2)}%</td>
                  <td>{item.earningsRevisionTrend}</td>
                  <td className="text-xs text-slate-500">{item.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
        <div className="card p-5">
          <p className="section-title">Market Data Coverage</p>
          <div className="space-y-2 text-sm text-slate-600">
            <div className="stat-row"><span className="stat-label">Daily Bars</span><span className="stat-value">{marketData?.dailyBarCount ?? 0}</span></div>
            <div className="stat-row"><span className="stat-label">Instruments</span><span className="stat-value">{marketData?.instrumentCount ?? 0}</span></div>
            {(marketData?.notes ?? []).map((note, index) => (
              <p key={index} className="text-xs text-slate-500">{note}</p>
            ))}
            {(dashboard?.notes ?? []).map((note, index) => (
              <p key={`dash-${index}`} className="text-xs text-slate-500">{note}</p>
            ))}
          </div>
        </div>

        <div className="card p-5">
          <div className="flex items-center gap-2 mb-4">
            <Newspaper className="w-4 h-4 text-slate-700" />
            <h3 className="font-bold text-slate-900">News Pulse</h3>
          </div>
          <div className="space-y-3">
            {(marketContext?.articles ?? []).slice(0, 6).map((article, index) => (
              <div key={`${article.headline}-${index}`} className="rounded-2xl border border-slate-100 bg-slate-50 px-4 py-3">
                <div className="flex flex-wrap items-center gap-2 mb-2">
                  <span className="text-sm font-semibold text-slate-900">{article.headline}</span>
                  <span className="badge badge-neutral">{article.source}</span>
                  <span className={`badge ${article.sentiment_score >= 0 ? 'badge-green' : 'badge-red'}`}>
                    Sentiment {formatSigned(article.sentiment_score)}
                  </span>
                </div>
                <p className="text-sm text-slate-600 leading-relaxed">{article.summary}</p>
                <div className="text-xs text-slate-500 mt-2">
                  Regions: {article.involved_regions.join(', ')} | Sectors: {article.affected_sectors.join(', ')}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
