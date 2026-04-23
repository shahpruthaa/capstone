import React, { useState, useEffect } from 'react';
import { Activity, TrendingUp, Brain, Zap, Database, Clock } from 'lucide-react';

export function OverviewTab() {
  const [systemMetrics, setSystemMetrics] = useState({
    latency: 45,
    artifactSize: 2.3,
    dataFreshness: 'Apr 21',
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
      <div className="metric-card">
        <div className="card-header">
          <Brain className="card-icon" />
          <h3>Ensemble Status</h3>
        </div>
        <div className="ensemble-health">
          <div className="health-bar">
            <div className="health-fill" style={{ width: `${systemMetrics.ensembleHealth}%` }} />
          </div>
          <div className="health-text">{systemMetrics.ensembleHealth}% Healthy</div>
        </div>
        <div className="model-status">
          <div className="status-item">
            <div className="status-dot active" />
            <span>LightGBM Model</span>
          </div>
          <div className="status-item">
            <div className="status-dot active" />
            <span>Rules Engine</span>
          </div>
          <div className="status-item">
            <div className="status-dot warning" />
            <span>News Sentiment</span>
          </div>
        </div>
      </div>

      {/* Market Regime Pulse */}
      <div className="metric-card">
        <div className="card-header">
          <TrendingUp className="card-icon" />
          <h3>Market Regime Pulse</h3>
        </div>
        <div className="regime-indicators">
          <div className="regime-item">
            <span className="label">Sentiment:</span>
            <span className={`value ${marketRegime.sentiment.toLowerCase()}`}>
              {marketRegime.sentiment}
            </span>
          </div>
          <div className="regime-item">
            <span className="label">Volatility:</span>
            <span className={`value ${marketRegime.volatility.toLowerCase()}`}>
              {marketRegime.volatility}
            </span>
          </div>
          <div className="regime-item">
            <span className="label">Leading Factors:</span>
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
      <div className="metric-card neural-signals">
        <div className="card-header">
          <Zap className="card-icon" />
          <h3>Neural Signals</h3>
        </div>
        <div className="signals-feed">
          {neuralSignals.map((signal, index) => (
            <div key={index} className="signal-item">
              <div className="signal-symbol">{signal.symbol}</div>
              <div className={`signal-action ${signal.signal.toLowerCase()}`}>
                {signal.signal}
              </div>
              <div className="signal-confidence">
                {(signal.confidence * 100).toFixed(0)}%
              </div>
              <div className="signal-time">{signal.timestamp}</div>
            </div>
          ))}
        </div>
      </div>

      {/* System Metrics */}
      <div className="metric-card">
        <div className="card-header">
          <Activity className="card-icon" />
          <h3>System Metrics</h3>
        </div>
        <div className="metrics-grid">
          <div className="metric-item">
            <Clock className="metric-icon" />
            <div className="metric-data">
              <div className="metric-value">{systemMetrics.latency}ms</div>
              <div className="metric-label">Avg Latency</div>
            </div>
          </div>
          <div className="metric-item">
            <Database className="metric-icon" />
            <div className="metric-data">
              <div className="metric-value">{systemMetrics.artifactSize}GB</div>
              <div className="metric-label">Model Size</div>
            </div>
          </div>
          <div className="metric-item">
            <Activity className="metric-icon" />
            <div className="metric-data">
              <div className="metric-value">{systemMetrics.dataFreshness}</div>
              <div className="metric-label">Data Freshness</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}