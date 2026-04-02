from __future__ import annotations
import json
import logging
from datetime import datetime, timezone
from typing import Any
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)

NSE_SECTORS = ["Banking", "IT", "Pharma", "Energy", "Auto", "FMCG",
               "Infra", "Finance", "Real Estate", "Telecom", "Gold", "Index"]

FALLBACK_SENTIMENT = {
    "sector_sentiment": {s: 0.0 for s in NSE_SECTORS},
    "stock_mentions": {},
    "geopolitical_risk": False,
    "geopolitical_risk_score": 0.0,
    "top_event_summary": "News analysis unavailable",
    "overall_market_sentiment": 0.0,
    "confidence": "none",
}

NEWS_PROMPT = """You are a financial analyst for Indian stock markets (NSE/BSE).

Today is {today}. Based on your knowledge of recent events up to today, analyse the current market environment for Indian stocks.

Consider:
1. Recent RBI monetary policy decisions
2. Global geopolitical events affecting India (US tariffs, oil prices, wars/conflicts)
3. FII/DII flows and rupee movement
4. Sector-specific news (IT exports, pharma US FDA, auto sales, banking NPA)
5. Any major corporate events in NSE-listed companies

For each NSE sector, provide a sentiment score:
- Positive = sector likely to outperform (-1.0 to +1.0)
- Base your analysis on events from the last 2 weeks

Respond ONLY with valid JSON, no markdown:
{{
  "sector_sentiment": {{
    "Banking": 0.0, "IT": 0.0, "Pharma": 0.0, "Energy": 0.0,
    "Auto": 0.0, "FMCG": 0.0, "Infra": 0.0, "Finance": 0.0,
    "Real Estate": 0.0, "Telecom": 0.0, "Gold": 0.0, "Index": 0.0
  }},
  "stock_mentions": {{}},
  "geopolitical_risk": false,
  "geopolitical_risk_score": 0.0,
  "top_event_summary": "one sentence summary of the most important current market event",
  "key_events": [],
  "overall_market_sentiment": 0.0,
  "confidence": "medium"
}}"""


async def get_market_context() -> dict[str, Any]:
    """Use Groq LLM knowledge to analyse current market context."""
    if not settings.groq_api_key:
        return {
            "market_context": FALLBACK_SENTIMENT,
            "headlines": [],
            "timestamp": datetime.utcnow().isoformat(),
            "source": "fallback_no_key",
        }

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    prompt = NEWS_PROMPT.format(today=today)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.groq_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.groq_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,
                    "max_tokens": 800,
                },
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"].strip()
            if "```" in content:
                parts = content.split("```")
                content = parts[1] if len(parts) > 1 else parts[0]
                if content.startswith("json"):
                    content = content[4:]
            result = json.loads(content.strip())
            result["analysed_at"] = datetime.utcnow().isoformat()
            result["source"] = "groq_knowledge"
            return {
                "market_context": result,
                "headlines": result.get("key_events", []),
                "timestamp": datetime.utcnow().isoformat(),
                "source": "groq_llm_knowledge",
                "note": "Analysis based on Groq LLM knowledge cutoff. For live news, connect an external news API."
            }
    except Exception as e:
        logger.error(f"Groq market context failed: {e}")
        return {
            "market_context": {**FALLBACK_SENTIMENT, "error": str(e)},
            "headlines": [],
            "timestamp": datetime.utcnow().isoformat(),
            "source": "error",
        }


def get_stock_news_risk_score(symbol: str, sector: str | None, market_context: dict[str, Any]) -> float:
    analysis = market_context.get("market_context", {})
    sector_sentiment = analysis.get("sector_sentiment", {})
    stock_mentions = analysis.get("stock_mentions", {})
    geo_risk = float(analysis.get("geopolitical_risk_score", 0.0))

    score = 0.0
    if sector and sector in sector_sentiment:
        score += float(sector_sentiment[sector]) * 0.6
    if symbol in stock_mentions:
        score += float(stock_mentions[symbol]) * 0.4
    score -= abs(geo_risk) * 0.3
    return float(max(-1.0, min(1.0, score)))
