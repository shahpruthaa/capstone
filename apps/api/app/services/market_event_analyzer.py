from __future__ import annotations

import logging

import httpx

from app.core.config import settings
from app.services.news_signal import build_market_news_context

logger = logging.getLogger(__name__)

MARKET_EVENT_ANALYSIS_PROMPT = """You are a senior market strategist at a top Indian investment bank.
Analyze the current market events and news for their impact on NSE sectors and stocks.

Current Market Context:
{market_context}

Recent News Articles:
{news_articles}

Market Regime: {regime_info}

Provide a comprehensive analysis covering:
1. Key market-moving events and their potential impact
2. Sector-specific implications and opportunities/risks
3. Trading recommendations based on current news flow
4. Risk management considerations
5. Timeline for expected market reactions

Be specific about which stocks/sectors are most affected and provide actionable insights for portfolio positioning."""


def analyze_market_events() -> str:
    """Generate comprehensive market event analysis using GenAI."""
    news_context = build_market_news_context()
    if not settings.groq_api_key:
        return build_fallback_market_event_analysis(news_context)

    try:
        news_articles = []
        for article in news_context.articles[:8]:
            news_articles.append(
                f"""
Article: {article.headline}
Source: {article.source}
Regions: {', '.join(article.involved_regions)}
Sectors: {', '.join(article.affected_sectors)}
Sentiment: {article.sentiment_score:+.2f}
Impact: {article.impact_score:.1f}/10
Summary: {article.explanation}
"""
            )

        regime_info = f"Overall Market Sentiment: {news_context.overall_market_sentiment:+.2f}"
        sector_sentiment = "\n".join(
            [f"- {sector}: {sentiment:+.2f}" for sector, sentiment in news_context.sector_sentiment.items()]
        )
        market_context = f"""
Overall Market Sentiment: {news_context.overall_market_sentiment:+.2f}
Sector Sentiment Breakdown:
{sector_sentiment}

Top Event Summary: {news_context.top_event_summary}
"""

        prompt = MARKET_EVENT_ANALYSIS_PROMPT.format(
            market_context=market_context,
            news_articles="\n".join(news_articles),
            regime_info=regime_info,
        )

        response = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.groq_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.groq_model,
                "max_tokens": 800,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
            },
            timeout=25,
        )

        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"].strip()

        logger.error("Market event analysis failed: %s", response.status_code)
        return build_fallback_market_event_analysis(news_context)
    except Exception as error:
        logger.error("Market event analysis error: %s", error)
        return build_fallback_market_event_analysis(news_context)


def build_fallback_market_event_analysis(news_context) -> str:
    strongest_sector = max(news_context.sector_sentiment.items(), key=lambda item: item[1], default=("Index", 0.0))
    weakest_sector = min(news_context.sector_sentiment.items(), key=lambda item: item[1], default=("Index", 0.0))
    market_tone = "supportive" if news_context.overall_market_sentiment >= 0 else "fragile"

    return (
        f"Market tone is currently {market_tone}, with aggregate news sentiment at {news_context.overall_market_sentiment:+.2f}. "
        f"The strongest sector impulse is in {strongest_sector[0]} ({strongest_sector[1]:+.2f}), while {weakest_sector[0]} is the weakest pocket ({weakest_sector[1]:+.2f}).\n\n"
        f"Top event: {news_context.top_event_summary}\n\n"
        "Use the strongest sectors for idea generation, keep tighter stops in the weakest sectors, and refresh this view as new headlines arrive. "
        "This summary is generated from the news-semantics layer when the GenAI explainer is unavailable."
    )
