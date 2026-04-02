"""Groq LLM explanation service for portfolio stock recommendations."""
from __future__ import annotations
import logging
from typing import Any
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)

EXPLAIN_PROMPT = """You are an expert NSE (National Stock Exchange of India) portfolio analyst. 
Explain why this stock was selected or rejected in a portfolio in 2-3 clear paragraphs.
Be specific about the numbers. Write for a sophisticated retail investor. No bullet points.

Stock: {symbol}
Sector: {sector}
Ensemble Score: {score:.3f} (range -1 to +1, higher = more attractive)
LightGBM Signal: {lgb_score:.3f}
LSTM Signal: {lstm_score:.3f}  
Death Risk: {death_risk:.3f} (0=safe, 1=high risk of blow-up)
News Sentiment: {news_sentiment:.3f}

Top Feature Drivers: {drivers}

Current Technicals:
- 21-day return: {ret_21d:.1%}
- 63-day return: {ret_63d:.1%}
- Volatility (21d): {vol_21d:.1%}
- Distance from 52-week high: {dist_52w:.1%}
- Beta: {beta:.2f}
- Sector: {sector}
- Market Cap Category: {market_cap}

Portfolio Context: {context}

Write a 2-3 paragraph explanation covering: (1) why the model scored this stock this way, 
(2) what the key risks or opportunities are, (3) what an investor should watch for.
Be direct and quantitative."""


def explain_stock(
    symbol: str,
    sector: str,
    score: float,
    lgb_score: float,
    lstm_score: float,
    death_risk: float,
    news_sentiment: float,
    drivers: list[str],
    technicals: dict[str, Any],
    portfolio_context: str = "MODERATE risk portfolio",
) -> str:
    """Call Groq to explain why a stock was scored the way it was."""
    if not settings.groq_api_key:
        return "LLM explanation unavailable — Groq API key not configured."

    prompt = EXPLAIN_PROMPT.format(
        symbol=symbol,
        sector=sector,
        score=score,
        lgb_score=lgb_score,
        lstm_score=lstm_score,
        death_risk=death_risk,
        news_sentiment=news_sentiment,
        drivers=", ".join(drivers[:5]) if drivers else "N/A",
        ret_21d=technicals.get("ret_21d", 0.0),
        ret_63d=technicals.get("ret_63d", 0.0),
        vol_21d=technicals.get("vol_21d", 0.0),
        dist_52w=technicals.get("dist_to_52w_high", 0.0),
        beta=technicals.get("beta_proxy", 1.0),
        market_cap=technicals.get("market_cap_bucket", "Unknown"),
        context=portfolio_context,
    )

    try:
        r = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.groq_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.groq_model,
                "max_tokens": 500,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
            },
            timeout=20,
        )
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"].strip()
        else:
            logger.error(f"Groq API error {r.status_code}: {r.text[:200]}")
            return f"LLM explanation temporarily unavailable (status {r.status_code})."
    except Exception as e:
        logger.error(f"Groq call failed: {e}")
        return "LLM explanation temporarily unavailable."


def explain_portfolio(
    allocations: list[dict[str, Any]],
    risk_mode: str,
    total_amount: float,
) -> str:
    """Generate a portfolio-level summary explanation."""
    if not settings.groq_api_key:
        return "LLM explanation unavailable."

    symbols_summary = ", ".join(
        f"{a['symbol']} ({a.get('weight', 0):.1f}%)"
        for a in allocations[:8]
    )
    sectors = list({a.get("sector", "Unknown") for a in allocations})

    prompt = f"""You are an NSE portfolio analyst. Summarize this AI-generated portfolio in 2 paragraphs.

Risk Mode: {risk_mode}
Investment Amount: ₹{total_amount:,.0f}
Top Holdings: {symbols_summary}
Seors Covered: {", ".join(sectors)}
Number of Holdings: {len(allocations)}

Explain: (1) what the portfolio is trying to achieve given the risk mode, 
(2) what themes or factors are driving the selection, 
(3) key risks to watch. Be specific and quantitative. No bullet points."""

    try:
        r = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.groq_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.groq_model,
                "max_tokens": 400,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
            },
            timeout=20,
        )
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"].strip()
        else:
            return "Portfolio summary unavailable."
    except Exception as e:
        logger.error(f"Groq portfolio explain failed: {e}")
        return "Portfolio summary unavailable."
