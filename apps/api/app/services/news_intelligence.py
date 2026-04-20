from __future__ import annotations

from app.services.ai_assistant import summarize_market_context
from app.services.news_signal import build_market_news_context


async def get_market_context() -> dict[str, object]:
    context = build_market_news_context()
    summary = await summarize_market_context(
        {
            "generated_at": context.generated_at,
            "articles": [
                {
                    "headline": article.headline,
                    "summary": article.summary,
                    "source": article.source,
                    "published_at": article.published_at,
                    "involved_regions": article.involved_regions,
                    "affected_sectors": article.affected_sectors,
                    "sentiment_score": article.sentiment_score,
                    "impact_score": article.impact_score,
                    "explanation": article.explanation,
                    "url": article.url,
                }
                for article in context.articles
            ],
            "sector_sentiment": context.sector_sentiment,
            "overall_market_sentiment": context.overall_market_sentiment,
            "top_event_summary": context.top_event_summary,
        }
    )
    return {
        "generated_at": context.generated_at,
        "articles": [
            {
                "headline": article.headline,
                "summary": article.summary,
                "source": article.source,
                "published_at": article.published_at,
                "involved_regions": article.involved_regions,
                "affected_sectors": article.affected_sectors,
                "sentiment_score": article.sentiment_score,
                "impact_score": article.impact_score,
                "explanation": article.explanation,
                "url": article.url,
            }
            for article in context.articles
        ],
        "sector_sentiment": context.sector_sentiment,
        "overall_market_sentiment": context.overall_market_sentiment,
        "top_event_summary": context.top_event_summary,
        "briefing": summary["briefing"],
        "actionable_takeaways": summary["actionable_takeaways"],
        "summary_source": summary["summary_source"],
    }
