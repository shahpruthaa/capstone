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
    if not settings.groq_api_key:
        return "LLM explanation unavailable."

    holding_lines = []
    for a in allocations[:10]:
        sym = a.get("symbol", "UNKNOWN")
        wt = float(a.get("weight", a.get("allocation", 0)) or 0)
        sector = a.get("sector", "")
        drivers = a.get("top_model_drivers", a.get("drivers", []))
        pred_21d = a.get("ml_pred_21d_return")
        pred_annual = a.get("ml_pred_annual_return")
        death_risk = a.get("death_risk")
        lstm = a.get("lstm_signal")

        line = f"- {sym}: {wt:.1f}%"
        if sector and sector not in ("Unknown", ""):
            line += f" | Sector: {sector}"
        if pred_21d is not None:
            line += f" | ML 21d: {float(pred_21d)*100:+.1f}%"
        if pred_annual is not None:
            line += f" | Annual forecast: {float(pred_annual)*100:+.1f}%"
        if death_risk is not None:
            line += f" | Death risk: {float(death_risk):.2f}"
        if lstm is not None:
            line += f" | LSTM: {float(lstm):+.2f}"
        if drivers:
            tech = [d for d in drivers if any(x in d for x in ["ema", "candle", "rsi", "macd", "bb", "adx", "atr"])][:2]
            others = [d for d in drivers if d not in tech and not d.startswith("lstm=") and not d.startswith("death_risk=")][:2]
            shown = (tech + others)[:3]
            if shown:
                line += f" | Signals: {', '.join(shown)}"
        holding_lines.append(line)

    holdings_text = "\n".join(holding_lines)
    sectors = list({a.get("sector", "") for a in allocations if a.get("sector") and a.get("sector") not in ("Unknown", "")})
    sectors_text = ", ".join(sectors) if sectors else "Diversified"
    active = sum(1 for a in allocations if float(a.get("weight", 0) or 0) > 0)

    prompt = f"""You are a senior NSE portfolio analyst at a top Indian asset management firm.

An AI ensemble model (LightGBM + LSTM + GNN + Death-Risk classifier) generated this portfolio:

Risk Mode: {risk_mode} | Investment: \u20b9{total_amount:,.0f} | Active positions: {active}
Sectors: {sectors_text}

Holdings with AI signals:
{holdings_text}

Write a 3-paragraph professional analysis:
Para 1: Portfolio objective — risk-return target, expected return range, construction philosophy for {risk_mode} mode.
Para 2: Interpret the AI signals — ema_21_above_50 means trend confirmed above 50-day EMA, candle_shooting_ means bearish reversal risk, high death_risk (>0.3) means crash risk, negative LSTM means sequence model is bearish, positive ML 21d forecast means model expects gains. Reference specific stocks.
Para 3: Key risks — concentration, sector exposure, specific stocks with warning signals (high death_risk or negative forecasts), what to monitor in current Indian market.
Be specific, professional, quantitative. Reference stock names and percentages. No bullet points."""
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
