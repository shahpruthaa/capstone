import React, { useState, useEffect } from 'react';
import { TrendingUp, AlertTriangle, Target, RefreshCw, CheckCircle, XCircle, Clock } from 'lucide-react';
import { Portfolio } from '../services/portfolioService';
import { postPortfolioRebalancing } from '../services/backendApi';

interface Props {
  portfolio: Portfolio | null;
}

interface RebalancingRecommendation {
  action: string;
  symbol: string;
  current_weight: number;
  target_weight: number;
  rationale: string;
  urgency: string;
  expected_impact: string;
}

interface RebalancingAnalysis {
  overall_assessment: string;
  risk_adjustment: string;
  timeline: string;
  explanation: string;
  recommendations: RebalancingRecommendation[];
}

export function RebalanceTab({ portfolio }: Props) {
  const [analysis, setAnalysis] = useState<RebalancingAnalysis | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchRebalancingAnalysis = async () => {
    if (!portfolio) return;

    setLoading(true);
    try {
      const result = await postPortfolioRebalancing(portfolio);
      setAnalysis(result);
    } catch (error) {
      console.error('Failed to fetch rebalancing analysis:', error);
      setAnalysis({
        overall_assessment: 'Analysis temporarily unavailable',
        risk_adjustment: 'Unable to assess',
        timeline: 'Unknown',
        explanation: 'Service temporarily unavailable. Please try again.',
        recommendations: []
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (portfolio) {
      fetchRebalancingAnalysis();
    }
  }, [portfolio]);

  const getActionIcon = (action: string) => {
    switch (action.toLowerCase()) {
      case 'buy':
        return <CheckCircle className="action-icon buy" />;
      case 'sell':
        return <XCircle className="action-icon sell" />;
      case 'hold':
        return <Clock className="action-icon hold" />;
      default:
        return <Target className="action-icon" />;
    }
  };

  const getUrgencyColor = (urgency: string) => {
    switch (urgency.toLowerCase()) {
      case 'high':
        return 'urgency-high';
      case 'medium':
        return 'urgency-medium';
      case 'low':
        return 'urgency-low';
      default:
        return 'urgency-low';
    }
  };

  if (!portfolio) {
    return (
      <div className="rebalance-empty">
        <Target className="empty-icon" />
        <h2>No Portfolio to Rebalance</h2>
        <p>Generate a portfolio first to access rebalancing analysis.</p>
      </div>
    );
  }

  return (
    <div className="rebalance-container">
      <div className="rebalance-header">
        <div className="header-content">
          <TrendingUp className="header-icon" />
          <div>
            <h1>Portfolio Rebalancing</h1>
            <p>AI-powered rebalancing recommendations with detailed explanations</p>
          </div>
        </div>
        <button
          className="refresh-button"
          onClick={fetchRebalancingAnalysis}
          disabled={loading}
        >
          <RefreshCw className={`refresh-icon ${loading ? 'spinning' : ''}`} />
          Refresh Analysis
        </button>
      </div>

      <div className="rebalance-overview">
        <div className="overview-card">
          <h3>Overall Assessment</h3>
          <p>{analysis?.overall_assessment || 'Loading...'}</p>
        </div>
        <div className="overview-card">
          <h3>Risk Adjustment</h3>
          <p>{analysis?.risk_adjustment || 'Loading...'}</p>
        </div>
        <div className="overview-card">
          <h3>Recommended Timeline</h3>
          <p>{analysis?.timeline || 'Loading...'}</p>
        </div>
      </div>

      {loading ? (
        <div className="loading-state">
          <RefreshCw className="loading-icon spinning" />
          <p>Analyzing portfolio for rebalancing opportunities...</p>
        </div>
      ) : analysis ? (
        <>
          <div className="rebalance-explanation">
            <h2>Detailed Analysis</h2>
            <div className="explanation-content">
              {analysis.explanation.split('\n').map((paragraph, index) => (
                <p key={index} className="analysis-paragraph">
                  {paragraph}
                </p>
              ))}
            </div>
          </div>

          {analysis.recommendations && analysis.recommendations.length > 0 && (
            <div className="recommendations-section">
              <h2>Specific Recommendations</h2>
              <div className="recommendations-grid">
                {analysis.recommendations.map((rec, index) => (
                  <div key={index} className="recommendation-card">
                    <div className="recommendation-header">
                      {getActionIcon(rec.action)}
                      <div>
                        <h3>{rec.symbol}</h3>
                        <span className={`urgency-badge ${getUrgencyColor(rec.urgency)}`}>
                          {rec.urgency} Priority
                        </span>
                      </div>
                    </div>
                    <div className="recommendation-details">
                      <div className="weight-change">
                        <span className="current">Current: {rec.current_weight.toFixed(1)}%</span>
                        <span className="target">Target: {rec.target_weight.toFixed(1)}%</span>
                      </div>
                      <p className="rationale">{rec.rationale}</p>
                      <p className="impact">
                        <strong>Expected Impact:</strong> {rec.expected_impact}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      ) : (
        <div className="no-analysis">
          <AlertTriangle className="no-analysis-icon" />
          <p>Unable to load rebalancing analysis. Please try again.</p>
        </div>
      )}
    </div>
  );
}