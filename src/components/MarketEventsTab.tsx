import React, { useState, useEffect } from 'react';
import { TrendingUp, AlertTriangle, Target, RefreshCw } from 'lucide-react';
import { getMarketEventsAnalysis } from '../services/backendApi';

export function MarketEventsTab() {
  const [analysis, setAnalysis] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<string>('');

  const fetchAnalysis = async () => {
    setLoading(true);
    try {
      const result = await getMarketEventsAnalysis();
      setAnalysis(result.analysis);
      setLastUpdated(result.generated_at);
    } catch (error) {
      setAnalysis('Failed to load market events analysis. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAnalysis();
  }, []);

  return (
    <div className="market-events-container">
      <div className="events-header">
        <div className="header-content">
          <TrendingUp className="header-icon" />
          <div>
            <h1>Market Events Analysis</h1>
            <p>Real-time news impact assessment and trading opportunities</p>
          </div>
        </div>
        <button
          className="refresh-button"
          onClick={fetchAnalysis}
          disabled={loading}
        >
          <RefreshCw className={`refresh-icon ${loading ? 'spinning' : ''}`} />
          Refresh
        </button>
      </div>

      {lastUpdated && (
        <div className="last-updated">
          Last updated: {new Date(lastUpdated).toLocaleString()}
        </div>
      )}

      <div className="events-content">
        {loading ? (
          <div className="loading-state">
            <RefreshCw className="loading-icon spinning" />
            <p>Analyzing market events...</p>
          </div>
        ) : (
          <div className="analysis-content">
            {analysis.split('\n').map((paragraph, index) => (
              <p key={index} className="analysis-paragraph">
                {paragraph}
              </p>
            ))}
          </div>
        )}
      </div>

      <div className="events-summary">
        <div className="summary-card">
          <AlertTriangle className="summary-icon warning" />
          <div>
            <h3>Risk Factors</h3>
            <p>Monitor geopolitical tensions and commodity price volatility</p>
          </div>
        </div>
        <div className="summary-card">
          <Target className="summary-icon opportunity" />
          <div>
            <h3>Opportunities</h3>
            <p>Focus on domestic consumption and IT sector stability</p>
          </div>
        </div>
      </div>
    </div>
  );
}