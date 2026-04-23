import React, { useState, useEffect } from 'react';
import { Activity, TrendingUp, Brain, Zap, Database, Clock } from 'lucide-react';

export function OverviewTab() {
  const [systemMetrics, setSystemMetrics] = useState({
    latency: 45,
    artifactSize: 2.3,
    dataFreshness: new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
    ensembleHealth: 98
  });

  const [marketRegime, setMarketRegime] = useState({
    sentiment: 'Bullish',
    volatility: 'Low',
    factors: ['Growth', 'Value']
  });

  const [neuralSignals, setNeuralSignals] = useState([
    { symbol: 'RELIANCE', signal: 'BUY', confidence: 0.87, timestamp: '14:32:15' },
    { symbol: 'TCS', signal: 'HOLD', confidence: 0.92, timestamp: '14:31:42' },
    { symbol: 'INFY', signal: 'SELL', confidence: 0.78, timestamp: '14:30:18' }
  ]);

  useEffect(() => {
    // Simulate real-time updates
    const interval = setInterval(() => {
      setNeuralSignals(prev => prev.map(signal => ({
        ...signal,
        confidence: Math.max(0.5, Math.min(1, signal.confidence + (Math.random() - 0.5) * 0.1))
      })));
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="overview-grid">
      {/* Ensemble Status */}
      <div className="bg-white border border-slate-200/80 rounded-2xl shadow-[0_2px_8px_rgb(0,0,0,0.04)] p-5">
        <div className="flex items-center gap-2 mb-4">
          <Brain className="w-4 h-4 text-blue-600" />
          <h3 className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em]">Ensemble Status</h3>
        </div>
        <div className="ensemble-health">
          <div className="health-bar">
            <div className="health-fill" style={{ width: `${systemMetrics.ensembleHealth}%` }} />
          </div>
          <div className="health-text text-slate-500">{systemMetrics.ensembleHealth}% Healthy</div>
        </div>
        <div className="model-status">
          <div className="status-item text-slate-900">
            <div className="status-dot active" />
            <span>LightGBM Model</span>
          </div>
          <div className="status-item text-slate-900">
            <div className="status-dot active" />
            <span>Rules Engine</span>
          </div>
          <div className="status-item text-slate-900">
            <div className="status-dot warning" />
            <span>News Sentiment</span>
          </div>
        </div>
      </div>

      {/* Market Regime Pulse */}
      <div className="bg-white border border-slate-200/80 rounded-2xl shadow-[0_2px_8px_rgb(0,0,0,0.04)] p-5">
        <div className="flex items-center gap-2 mb-4">
          <TrendingUp className="w-4 h-4 text-emerald-600" />
          <h3 className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em]">Market Regime Pulse</h3>
        </div>
        <div className="regime-indicators">
          <div className="regime-item">
            <span className="label text-slate-500">Sentiment:</span>
            <span className={`value ${marketRegime.sentiment.toLowerCase()} text-slate-900`}>
              {marketRegime.sentiment}
            </span>
          </div>
          <div className="regime-item">
            <span className="label text-slate-500">Volatility:</span>
            <span className={`value ${marketRegime.volatility.toLowerCase()} text-slate-900`}>
              {marketRegime.volatility}
            </span>
          </div>
          <div className="regime-item">
            <span className="label text-slate-500">Leading Factors:</span>
            <div className="factors">
              {marketRegime.factors.map(factor => (
                <span key={factor} className="factor-tag">{factor}</span>
              ))}
            </div>
          </div>
        </div>
        <div className="regime-chart">
          {/* Placeholder for factor weather chart */}
          <div className="chart-placeholder">
            <div className="factor-bar growth" style={{ height: '70%' }} />
            <div className="factor-bar value" style={{ height: '45%' }} />
            <div className="factor-bar momentum" style={{ height: '60%' }} />
          </div>
        </div>
      </div>

      {/* Neural Signals */}
      <div className="bg-white border border-slate-200/80 rounded-2xl shadow-[0_2px_8px_rgb(0,0,0,0.04)] p-5 neural-signals">
        <div className="flex items-center gap-2 mb-4">
          <Zap className="w-4 h-4 text-amber-500" />
          <h3 className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em]">Neural Signals</h3>
        </div>
        <div className="signals-feed">
          {neuralSignals.map((signal, index) => (
            <div key={index} className="signal-item bg-slate-50">
              <div className="signal-symbol text-slate-900 font-bold">{signal.symbol}</div>
              <div className={`signal-action ${signal.signal.toLowerCase()}`}>
                {signal.signal}
              </div>
              <div className="signal-confidence font-mono text-[10px] text-slate-500 uppercase">
                {(signal.confidence * 100).toFixed(0)}% CONFIDENCE
              </div>
              <div className="text-slate-400 font-mono text-[10px]">{signal.timestamp}</div>
            </div>
          ))}
        </div>
      </div>

      {/* System Metrics */}
      <div className="bg-white border border-slate-200/80 rounded-2xl shadow-[0_2px_8px_rgb(0,0,0,0.04)] p-5">
        <div className="flex items-center gap-2 mb-4">
          <Activity className="w-4 h-4 text-rose-500" />
          <h3 className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.08em]">System Metrics</h3>
        </div>
        <div className="metrics-grid">
          <div className="metric-item bg-slate-50">
            <Clock className="metric-icon" />
            <div className="metric-data">
              <div className="metric-value font-mono text-slate-900">{systemMetrics.latency}ms</div>
              <div className="metric-label text-slate-500">Avg Latency</div>
            </div>
          </div>
          <div className="metric-item bg-slate-50">
            <Database className="metric-icon" />
            <div className="metric-data">
              <div className="metric-value font-mono text-slate-900">{systemMetrics.artifactSize}GB</div>
              <div className="metric-label text-slate-500">Model Size</div>
            </div>
          </div>
          <div className="metric-item bg-slate-50">
            <Activity className="metric-icon" />
            <div className="metric-data">
              <div className="metric-value font-mono text-slate-900">{systemMetrics.dataFreshness}</div>
              <div className="metric-label text-slate-500">Data Freshness</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}