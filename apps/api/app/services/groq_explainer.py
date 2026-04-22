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


def _fallback_stock_explanation(
    symbol: str,
    sector: str,
    score: float,
    death_risk: float,
    drivers: list[str],
    technicals: dict[str, Any],
) -> str:
    driver_text = f" Top drivers: {', '.join(drivers[:3])}." if drivers else ""
    return (
        f"{symbol} sits in {sector} with beta {float(technicals.get('beta_proxy', 1.0)):.2f}, "
        f"21-day return {float(technicals.get('ret_21d', 0.0)):.1%}, 63-day return {float(technicals.get('ret_63d', 0.0)):.1%}, "
        f"and 21-day volatility {float(technicals.get('vol_21d', 0.0)):.1%}. "
        f"The current ensemble score is {score:+.2f} and death risk is {death_risk:.2f}.{driver_text}"
    )


def _fallback_portfolio_explanation(
    allocations: list[dict[str, Any]],
    risk_mode: str,
    total_amount: float,
) -> str:
    active = [allocation for allocation in allocations if float(allocation.get("weight", 0) or 0) > 0]
    top_holdings = ", ".join(
        f"{allocation.get('symbol', 'UNKNOWN')} {float(allocation.get('weight', 0) or 0):.1f}%"
        for allocation in sorted(active, key=lambda item: float(item.get("weight", 0) or 0), reverse=True)[:5]
    )
    sector_totals: dict[str, float] = {}
    for allocation in active:
        sector = str(allocation.get("sector") or "Unknown")
        sector_totals[sector] = sector_totals.get(sector, 0.0) + float(allocation.get("weight", 0) or 0.0)
    sector_text = ", ".join(
        f"{sector} {weight:.1f}%"
        for sector, weight in sorted(sector_totals.items(), key=lambda item: item[1], reverse=True)[:4]
    )
    return (
        f"This {risk_mode} portfolio deploys Rs{total_amount:,.0f} across {len(active)} active positions. "
        f"The largest holdings are {top_holdings or 'not available'}, with sector exposure led by {sector_text or 'diversified exposure'}. "
        f"Use the ensemble forecasts, risk notes, and news context on each holding to judge which names carry the return thesis versus diversification ballast."
    )


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
    if not settings.groq_api_key:
        return _fallback_stock_explanation(symbol, sector, score, death_risk, drivers, technicals)

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
        response = httpx.post(
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
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        logger.error(f"Groq stock explanation failed: {exc}")

    return _fallback_stock_explanation(symbol, sector, score, death_risk, drivers, technicals)


def explain_portfolio(
    allocations: list[dict[str, Any]],
    risk_mode: str,
    total_amount: float,
) -> str:
    if not settings.groq_api_key:
        return _fallback_portfolio_explanation(allocations, risk_mode, total_amount)

    holding_lines = []
    for allocation in allocations[:10]:
        symbol = allocation.get("symbol", "UNKNOWN")
        weight = float(allocation.get("weight", allocation.get("allocation", 0)) or 0)
        sector = allocation.get("sector", "")
        drivers = allocation.get("top_model_drivers", allocation.get("drivers", []))
        pred_21d = allocation.get("ml_pred_21d_return")
        pred_annual = allocation.get("ml_pred_annual_return")
        death_risk = allocation.get("death_risk")
        lstm_signal = allocation.get("lstm_signal")

        line = f"- {symbol}: {weight:.1f}%"
        if sector and sector not in ("Unknown", ""):
            line += f" | Sector: {sector}"
        if pred_21d is not None:
            line += f" | ML 21d: {float(pred_21d) * 100:+.1f}%"
        if pred_annual is not None:
            line += f" | Annual forecast: {float(pred_annual) * 100:+.1f}%"
        if death_risk is not None:
            line += f" | Death risk: {float(death_risk):.2f}"
        if lstm_signal is not None:
            line += f" | LSTM: {float(lstm_signal):+.2f}"
        if drivers:
            line += f" | Signals: {', '.join(drivers[:3])}"
        holding_lines.append(line)

    prompt = f"""You are a senior NSE portfolio analyst at a top Indian asset management firm.

An AI ensemble model generated this portfolio:

Risk Mode: {risk_mode} | Investment: Rs{total_amount:,.0f}
Holdings with AI signals:
{chr(10).join(holding_lines)}

Write a 3-paragraph professional analysis:
Para 1: Portfolio objective and construction philosophy.
Para 2: Interpret the AI signals and reference specific stocks.
Para 3: Key risks, concentration, and what to monitor next.
Be specific, professional, quantitative, and do not use bullet points."""

    try:
        response = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.groq_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.groq_model,
                "max_tokens": 450,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
            },
            timeout=20,
        )
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        logger.error(f"Groq portfolio explanation failed: {exc}")

    return _fallback_portfolio_explanation(allocations, risk_mode, total_amount)
