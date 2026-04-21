from __future__ import annotations
import logging
from typing import Any, List
from dataclasses import dataclass
import httpx
from app.core.config import settings
from app.services.news_signal import build_market_news_context
from app.ingestion.market_regime import build_market_regime_snapshot
from app.services.db_quant_engine import get_effective_trade_date
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

@dataclass
class RebalancingRecommendation:
    action: str  # "BUY", "SELL", "HOLD"
    symbol: str
    current_weight: float
    target_weight: float
    rationale: str
    urgency: str  # "HIGH", "MEDIUM", "LOW"
    expected_impact: str

@dataclass
class RebalancingAnalysis:
    recommendations: List[RebalancingRecommendation]
    overall_assessment: str
    risk_adjustment: str
    timeline: str
    explanation: str

REBALANCING_ANALYSIS_PROMPT = """You are a senior portfolio manager at a leading Indian asset management firm.
Analyze the current portfolio and provide detailed rebalancing recommendations.

Current Portfolio Holdings:
{portfolio_holdings}

Portfolio Mandate:
{risk_profile} | {investment_horizon} | Target: ₹{total_value:,.0f}

Market Context:
{market_regime}

News Impact:
{news_context}

Current Model Signals:
{model_signals}

Provide a comprehensive rebalancing analysis covering:

1. **Overall Portfolio Assessment**: Health, diversification, risk alignment
2. **Individual Position Reviews**: Which stocks to buy/sell/hold and why
3. **Risk Management**: Any concentration or sector risks to address
4. **Timeline**: When to implement changes (immediate, quarterly, etc.)
5. **Expected Impact**: How rebalancing affects risk-return profile

For each recommendation, specify:
- Action (BUY/SELL/HOLD)
- Target weight change
- Rationale with specific numbers
- Urgency level
- Expected portfolio impact

Be quantitative, specific about stock names, percentages, and timeframes."""

def analyze_portfolio_rebalancing(
    db: Session,
    allocations: List[dict],
    risk_profile: str,
    investment_horizon: str,
    total_value: float
) -> RebalancingAnalysis:
    """Generate comprehensive portfolio rebalancing analysis with GenAI."""
    if not settings.groq_api_key:
        return RebalancingAnalysis(
            recommendations=[],
            overall_assessment="Rebalancing analysis unavailable — GenAI service not configured.",
            risk_adjustment="Unable to assess",
            timeline="Unknown",
            explanation="Service temporarily unavailable"
        )

    try:
        # Get current market context
        as_of_date = get_effective_trade_date(db)
        market_regime = build_market_regime_snapshot(db, trade_date=as_of_date)
        news_context = build_market_news_context()

        # Format portfolio holdings
        portfolio_holdings = []
        for alloc in allocations[:15]:  # Limit for prompt size
            symbol = alloc.get('symbol', 'UNKNOWN')
            weight = float(alloc.get('weight', 0))
            sector = alloc.get('sector', 'Unknown')
            ml_signal = alloc.get('ml_pred_21d_return')
            death_risk = alloc.get('death_risk')

            holding_info = f"- {symbol} ({sector}): {weight:.1f}%"
            if ml_signal is not None:
                holding_info += f" | ML 21d: {float(ml_signal)*100:+.1f}%"
            if death_risk is not None:
                holding_info += f" | Death Risk: {float(death_risk):.2f}"
            portfolio_holdings.append(holding_info)

        # Format market regime
        regime_info = "Market regime data unavailable"
        if market_regime:
            regime_info = f"""
Regime: {market_regime.get('regime', 'Unknown').upper()}
Confidence: {market_regime.get('confidence', '0')}% | Nifty: {market_regime.get('nifty_level', 'N/A')}
Breadth 50d: {market_regime.get('breadth_50', 'N/A')}% | Breadth 200d: {market_regime.get('breadth_200', 'N/A')}%
VIX: {market_regime.get('india_vix', 'N/A')}"""

        # Format news context
        news_summary = f"Overall Sentiment: {news_context.overall_market_sentiment:+.2f}"
        top_sectors = sorted(news_context.sector_sentiment.items(), key=lambda x: abs(x[1]), reverse=True)[:5]
        news_summary += "\nTop Sector Impacts: " + ", ".join([f"{s}: {sent:+.2f}" for s, sent in top_sectors])

        # Format model signals (simplified for now)
        model_signals = "Current ensemble model active with multi-factor signals"

        prompt = REBALANCING_ANALYSIS_PROMPT.format(
            portfolio_holdings="\n".join(portfolio_holdings),
            risk_profile=risk_profile,
            investment_horizon=investment_horizon,
            total_value=total_value,
            market_regime=regime_info,
            news_context=news_summary,
            model_signals=model_signals
        )

        response = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.groq_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.groq_model,
                "max_tokens": 1000,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,  # Lower temperature for more consistent analysis
            },
            timeout=30,
        )

        if response.status_code == 200:
            analysis_text = response.json()["choices"][0]["message"]["content"].strip()

            # Parse recommendations from the analysis (simplified parsing)
            recommendations = []
            # This is a basic implementation - in production, you'd want more sophisticated parsing

            return RebalancingAnalysis(
                recommendations=recommendations,  # Would be parsed from analysis_text
                overall_assessment="Portfolio rebalancing analysis completed",
                risk_adjustment="Analysis provided in detailed explanation",
                timeline="Based on market conditions and model signals",
                explanation=analysis_text
            )
        else:
            logger.error(f"Rebalancing analysis failed: {response.status_code}")
            return RebalancingAnalysis(
                recommendations=[],
                overall_assessment="Analysis temporarily unavailable",
                risk_adjustment="Unable to assess",
                timeline="Unknown",
                explanation="Service temporarily unavailable"
            )

    except Exception as e:
        logger.error(f"Rebalancing analysis error: {e}")
        return RebalancingAnalysis(
            recommendations=[],
            overall_assessment="Analysis temporarily unavailable",
            risk_adjustment="Unable to assess",
            timeline="Unknown",
            explanation="Service temporarily unavailable"
        )