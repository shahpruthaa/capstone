from __future__ import annotations

import json
import logging
import re
from calendar import monthrange
from datetime import datetime
from typing import Any

import httpx

from app.core.config import settings
from app.services.mandate import NSE_SECTOR_CODES, normalize_sector_code


logger = logging.getLogger(__name__)

MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


async def _groq_completion(
    *,
    messages: list[dict[str, str]],
    max_tokens: int = 500,
    temperature: float = 0.3,
) -> str | None:
    if not settings.groq_api_key:
        return None

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.groq_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.groq_model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
            )
        if response.status_code != 200:
            logger.error("Groq API error %s: %s", response.status_code, response.text[:300])
            return None
        payload = response.json()
        return payload["choices"][0]["message"]["content"].strip()
    except Exception as exc:  # pragma: no cover - best-effort network path
        logger.error("Groq completion failed: %s", exc)
        return None


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _extract_amount(text: str) -> float | None:
    match = re.search(
        r"(?:₹|rs\.?|inr)?\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(crore|cr|lakh|lakhs|lac|lacs|k)?",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    number = float(match.group(1).replace(",", ""))
    unit = (match.group(2) or "").lower()
    if unit in {"crore", "cr"}:
        return number * 10_000_000
    if unit in {"lakh", "lakhs", "lac", "lacs"}:
        return number * 100_000
    if unit == "k":
        return number * 1_000
    return number


def _extract_horizon(text: str) -> str | None:
    normalized = text.lower().replace("–", "-").replace("to", "-")
    for option in ("2-4", "4-8", "8-24"):
        if option in normalized:
            return option

    weeks_match = re.search(r"(\d{1,2})\s*weeks?", normalized)
    if weeks_match:
        weeks = int(weeks_match.group(1))
        if weeks <= 4:
            return "2-4"
        if weeks <= 8:
            return "4-8"
        return "8-24"
    return None


def _extract_risk_attitude(text: str) -> str | None:
    normalized = text.lower()
    if any(token in normalized for token in ["capital preservation", "conservative", "low risk", "ultra low"]):
        return "capital_preservation"
    if any(token in normalized for token in ["balanced", "moderate", "medium risk"]):
        return "balanced"
    if any(token in normalized for token in ["growth", "aggressive", "high risk"]):
        return "growth"
    return None


def _extract_sector_filters(text: str) -> tuple[list[str], list[str]]:
    normalized = text.lower()
    includes: list[str] = []
    excludes: list[str] = []

    for sector in NSE_SECTOR_CODES:
        token = sector.lower()
        if re.search(rf"(avoid|exclude|without|no)\s+{re.escape(token)}", normalized):
            excludes.append(normalize_sector_code(sector))
        elif re.search(rf"(include|with|add|prefer|focus on)\s+{re.escape(token)}", normalized):
            includes.append(normalize_sector_code(sector))

    return sorted(set(includes)), sorted(set(excludes))


def _extract_small_cap_preference(text: str) -> bool | None:
    normalized = text.lower()
    if "small cap" not in normalized and "small-cap" not in normalized:
        return None
    if any(token in normalized for token in ["no small cap", "no small-cap", "avoid small cap", "avoid small-cap", "without small cap"]):
        return False
    return True


def _extract_month_year(text: str) -> tuple[int, int] | None:
    match = re.search(
        r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t|tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+(\d{4})\b",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    month = MONTHS[match.group(1).lower()]
    year = int(match.group(2))
    return year, month


def _month_start(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}-01"


def _month_end(year: int, month: int) -> str:
    last_day = monthrange(year, month)[1]
    return f"{year:04d}-{month:02d}-{last_day:02d}"


def _extract_backtest_window(text: str) -> tuple[str | None, str | None]:
    iso_dates = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", text)
    if len(iso_dates) >= 2:
        return iso_dates[0], iso_dates[1]

    years = re.findall(r"\b(20\d{2})\b", text)
    if len(years) >= 2:
        return f"{years[0]}-01-01", f"{years[1]}-12-31"
    if len(years) == 1 and "backtest" in text.lower():
        return f"{years[0]}-01-01", f"{years[0]}-12-31"

    month_year = _extract_month_year(text)
    if month_year:
        year, month = month_year
        return _month_start(year, month), _month_end(year, month)

    return None, None


def _extract_rebalance_frequency(text: str) -> str | None:
    normalized = text.lower()
    if "monthly" in normalized:
        return "Monthly"
    if "quarterly" in normalized:
        return "Quarterly"
    if "annual" in normalized or "yearly" in normalized:
        return "Annually"
    if "no rebalance" in normalized or "without rebalance" in normalized:
        return "None"
    return None


def _extract_percent(text: str, label: str) -> float | None:
    match = re.search(rf"{label}\s*(?:at|of|to)?\s*(\d{{1,2}}(?:\.\d+)?)\s*%", text, flags=re.IGNORECASE)
    if not match:
        return None
    return float(match.group(1)) / 100.0


def _portfolio_context_block(portfolio: dict[str, Any]) -> str:
    allocations = portfolio.get("allocations", [])[:8]
    if not allocations:
        return "No active portfolio."
    lines = []
    for allocation in allocations:
        lines.append(
            "- {symbol}: {weight:.1f}% | {sector} | ML21D {ml:+.1f}% | Death risk {risk:.2f}".format(
                symbol=allocation.get("symbol", "UNKNOWN"),
                weight=_safe_float(allocation.get("weight")),
                sector=allocation.get("sector", "Unknown"),
                ml=_safe_float(allocation.get("ml_pred_21d_return")) * 100.0,
                risk=_safe_float(allocation.get("death_risk")),
            )
        )
    metrics = portfolio.get("metrics", {})
    return "\n".join(
        [
            "Active portfolio:",
            f"Total invested: ₹{_safe_float(portfolio.get('total_invested')):,.0f}",
            f"Expected return: {_safe_float(metrics.get('estimated_annual_return')):.1f}%",
            f"Expected volatility: {_safe_float(metrics.get('estimated_volatility')):.1f}%",
            *lines,
        ]
    )


def _trade_ideas_block(trade_ideas: list[dict[str, Any]]) -> str:
    if not trade_ideas:
        return "No trade ideas loaded."
    lines = []
    for idea in trade_ideas[:5]:
        lines.append(
            "- {symbol}: checklist {score}/10 | exp return {ret:+.1f}% | RR {rr:.2f} | catalyst {catalyst}".format(
                symbol=idea.get("symbol", "UNKNOWN"),
                score=int(_safe_float(idea.get("checklist_score"), 0)),
                ret=_safe_float(idea.get("expected_return_annual")) * 100.0,
                rr=_safe_float(idea.get("risk_reward_ratio")),
                catalyst=idea.get("catalyst") or "n/a",
            )
        )
    return "\n".join(["Top trade ideas:", *lines])


def _backtest_block(backtest: dict[str, Any]) -> str:
    if not backtest:
        return "No backtest loaded."
    return "\n".join(
        [
            "Latest backtest:",
            f"Total return: {_safe_float(backtest.get('total_return')):+.2f}%",
            f"CAGR: {_safe_float(backtest.get('cagr')):+.2f}%",
            f"Max drawdown: {_safe_float(backtest.get('max_drawdown')):.2f}%",
            f"Sharpe: {_safe_float(backtest.get('sharpe')):.2f}",
            f"Win rate: {_safe_float(backtest.get('win_rate')):.1f}%",
            f"Trades: {int(_safe_float(backtest.get('total_trades'), 0))}",
        ]
    )


def _market_block(market_context: dict[str, Any]) -> str:
    if not market_context:
        return "No market context loaded."
    articles = market_context.get("articles", [])[:3]
    lines = [
        "Market context:",
        f"Overall sentiment: {_safe_float(market_context.get('overall_market_sentiment')):+.2f}",
        f"Briefing: {market_context.get('briefing') or market_context.get('top_event_summary') or 'n/a'}",
    ]
    for article in articles:
        lines.append(
            "- {headline} | sentiment {sentiment:+.2f} | impact {impact:.1f}/10".format(
                headline=article.get("headline", "Untitled"),
                sentiment=_safe_float(article.get("sentiment_score")),
                impact=_safe_float(article.get("impact_score")),
            )
        )
    return "\n".join(lines)


def render_grounded_context(grounded_context: dict[str, Any]) -> str:
    return "\n\n".join(
        [
            f"Active tab: {grounded_context.get('active_tab', 'UNKNOWN')}",
            _portfolio_context_block(grounded_context.get("portfolio") or {}),
            _trade_ideas_block(grounded_context.get("trade_ideas") or []),
            _backtest_block(grounded_context.get("backtest") or {}),
            _market_block(grounded_context.get("market_context") or {}),
        ]
    )


def infer_action(message: str, grounded_context: dict[str, Any]) -> dict[str, Any] | None:
    normalized = message.lower()
    has_portfolio = bool((grounded_context.get("portfolio") or {}).get("allocations"))

    if any(token in normalized for token in ["trade ideas", "trade idea", "scan ideas", "load ideas", "refresh ideas"]):
        return {
            "type": "load_trade_ideas",
            "label": "Load trade ideas",
            "auto_execute": True,
            "blocked_reason": None,
            "params": {},
        }

    if any(token in normalized for token in ["market pulse", "refresh market", "refresh news", "market context", "market summary"]):
        return {
            "type": "refresh_market",
            "label": "Refresh market pulse",
            "auto_execute": True,
            "blocked_reason": None,
            "params": {},
        }

    if any(token in normalized for token in ["backtest", "simulate", "replay"]) and (
        any(token in normalized for token in ["run", "start", "do", "launch"]) or normalized.strip().startswith("backtest")
    ):
        start_date, end_date = _extract_backtest_window(message)
        action = {
            "type": "run_backtest",
            "label": "Run backtest",
            "auto_execute": True,
            "blocked_reason": None if has_portfolio else "Generate a portfolio first so there is something concrete to replay.",
            "params": {
                "start_date": start_date,
                "end_date": end_date,
                "rebalance_frequency": _extract_rebalance_frequency(message),
                "stop_loss_pct": _extract_percent(message, "stop(?:[- ]loss)?"),
                "take_profit_pct": _extract_percent(message, "take(?:[- ]profit)?|target"),
            },
        }
        return action

    if any(token in normalized for token in ["portfolio", "basket", "allocation"]) and any(token in normalized for token in ["generate", "build", "create", "make"]):
        sector_inclusions, sector_exclusions = _extract_sector_filters(message)
        params = {
            "capital_amount": _extract_amount(message) or 500_000.0,
            "risk_attitude": _extract_risk_attitude(message) or "balanced",
            "investment_horizon_weeks": _extract_horizon(message) or "4-8",
            "sector_inclusions": sector_inclusions,
            "sector_exclusions": sector_exclusions,
            "allow_small_caps": _extract_small_cap_preference(message),
        }
        return {
            "type": "generate_portfolio",
            "label": "Generate portfolio",
            "auto_execute": True,
            "blocked_reason": None,
            "params": params,
        }

    return None


def _deterministic_copilot_reply(message: str, grounded_context: dict[str, Any], action: dict[str, Any] | None) -> str:
    if action and action.get("blocked_reason"):
        return action["blocked_reason"]

    if action:
        if action["type"] == "generate_portfolio":
            params = action["params"]
            return (
                "I parsed this as a portfolio-generation request. "
                f"I'll use ₹{_safe_float(params.get('capital_amount')):,.0f}, "
                f"{str(params.get('risk_attitude', 'balanced')).replace('_', ' ')}, "
                f"and a {params.get('investment_horizon_weeks', '4-8')} week horizon."
            )
        if action["type"] == "run_backtest":
            params = action["params"]
            start = params.get("start_date") or "the default window"
            end = params.get("end_date") or "the latest available date"
            return f"I read that as a backtest request. I'll replay the current portfolio from {start} to {end}."
        if action["type"] == "load_trade_ideas":
            return "I read that as a trade-idea scan request. I'll refresh the checklist-driven idea set now."
        if action["type"] == "refresh_market":
            return "I read that as a market/news refresh request. I'll update the market pulse now."

    portfolio = grounded_context.get("portfolio") or {}
    backtest = grounded_context.get("backtest") or {}
    market_context = grounded_context.get("market_context") or {}
    normalized = message.lower()

    if "portfolio" in normalized and portfolio.get("allocations"):
        metrics = portfolio.get("metrics") or {}
        return (
            "The active portfolio is already loaded. "
            f"It is targeting about {_safe_float(metrics.get('estimated_annual_return')):.1f}% annual return "
            f"with {_safe_float(metrics.get('estimated_volatility')):.1f}% expected volatility, "
            f"and the biggest current weights are "
            + ", ".join(
                f"{allocation.get('symbol', 'UNKNOWN')} ({_safe_float(allocation.get('weight')):.1f}%)"
                for allocation in (portfolio.get("allocations") or [])[:3]
            )
            + "."
        )

    if "backtest" in normalized and backtest:
        return (
            f"The latest backtest shows {_safe_float(backtest.get('total_return')):+.2f}% total return, "
            f"{_safe_float(backtest.get('cagr')):+.2f}% CAGR, and "
            f"{_safe_float(backtest.get('max_drawdown')):.2f}% max drawdown."
        )

    if any(token in normalized for token in ["market", "news", "sector"]) and market_context:
        return str(market_context.get("briefing") or market_context.get("top_event_summary") or "The market context is loaded and ready.")

    return (
        "I can help with the live portfolio, trade ideas, backtests, and market pulse. "
        "You can ask me to generate a portfolio, run a backtest, refresh trade ideas, or summarize the current setup."
    )


async def chat_with_copilot(
    *,
    message: str,
    history: list[dict[str, Any]],
    grounded_context: dict[str, Any],
) -> dict[str, Any]:
    action = infer_action(message, grounded_context)
    if not settings.groq_api_key:
        return {"response": _deterministic_copilot_reply(message, grounded_context, action), "action": action}

    context_block = render_grounded_context(grounded_context)
    action_block = json.dumps(action or {}, ensure_ascii=True)
    messages = [
        {
            "role": "system",
            "content": (
                "You are AlphaLens Copilot for an NSE portfolio research app. "
                "Stay grounded in the supplied application context. "
                "Do not invent holdings, returns, trade ideas, or market events that are not present. "
                "Use concise investor-facing prose. If an action candidate is present, acknowledge it briefly because the UI may execute it."
            ),
        },
        {
            "role": "system",
            "content": f"Grounded app context:\n{context_block}\n\nAction candidate:\n{action_block}",
        },
    ]
    for item in history[-6:]:
        role = str(item.get("role", "user"))
        if role not in {"user", "assistant"}:
            continue
        messages.append({"role": role, "content": str(item.get("content", ""))})
    messages.append({"role": "user", "content": message})

    completion = await _groq_completion(messages=messages, max_tokens=450, temperature=0.25)
    if not completion:
        completion = _deterministic_copilot_reply(message, grounded_context, action)
    return {"response": completion, "action": action}


def _top_sector_takeaways(sector_sentiment: dict[str, float]) -> list[str]:
    if not sector_sentiment:
        return ["No sector sentiment signals are available yet."]
    ordered = sorted(sector_sentiment.items(), key=lambda item: abs(item[1]), reverse=True)[:3]
    takeaways = []
    for sector, score in ordered:
        tone = "tailwind" if score >= 0 else "headwind"
        takeaways.append(f"{sector}: {tone} at {score:+.2f} sentiment.")
    return takeaways


async def summarize_market_context(payload: dict[str, Any]) -> dict[str, Any]:
    sector_sentiment = payload.get("sector_sentiment") or {}
    top_event_summary = str(payload.get("top_event_summary") or "No major event summary is available.")
    takeaways = _top_sector_takeaways(sector_sentiment)

    if not settings.groq_api_key:
        direction = "constructive" if _safe_float(payload.get("overall_market_sentiment")) >= 0 else "defensive"
        briefing = (
            f"The current news backdrop is {direction} for Indian equities. "
            f"Most of the narrative is being driven by: {top_event_summary}"
        )
        return {"briefing": briefing, "actionable_takeaways": takeaways, "summary_source": "rules"}

    article_lines = []
    for article in (payload.get("articles") or [])[:6]:
        article_lines.append(
            "- {headline} | sectors: {sectors} | sentiment {sentiment:+.2f} | impact {impact:.1f}/10 | summary: {summary}".format(
                headline=article.get("headline", "Untitled"),
                sectors=", ".join(article.get("affected_sectors", [])[:3]) or "n/a",
                sentiment=_safe_float(article.get("sentiment_score")),
                impact=_safe_float(article.get("impact_score")),
                summary=article.get("summary", ""),
            )
        )

    messages = [
        {
            "role": "system",
            "content": (
                "You are summarizing Indian market news for an NSE portfolio workstation. "
                "Write one concise paragraph that links the biggest current events to sector-level portfolio implications. "
                "Do not use bullets."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Overall market sentiment: {_safe_float(payload.get('overall_market_sentiment')):+.2f}\n"
                f"Top event summary: {top_event_summary}\n"
                f"Sector sentiment map: {json.dumps(sector_sentiment, ensure_ascii=True)}\n"
                "Articles:\n"
                + "\n".join(article_lines)
            ),
        },
    ]
    completion = await _groq_completion(messages=messages, max_tokens=220, temperature=0.2)
    briefing = completion or (
        f"The current market backdrop is being led by {top_event_summary} while the strongest sector moves remain "
        + ", ".join(takeaways[:2])
        + "."
    )
    return {"briefing": briefing, "actionable_takeaways": takeaways, "summary_source": "llm" if completion else "rules"}


async def explain_trade_idea(idea: dict[str, Any], portfolio_context: dict[str, Any] | None = None) -> str:
    symbol = idea.get("symbol", "UNKNOWN")
    fallback = (
        f"{symbol} clears the checklist with a {int(_safe_float(idea.get('checklist_score'), 0))}/10 score, "
        f"expected annual return of {_safe_float(idea.get('expected_return_annual')) * 100.0:+.1f}%, "
        f"and risk/reward of {_safe_float(idea.get('risk_reward_ratio')):.2f}:1. "
        f"The main catalyst is {idea.get('catalyst') or 'the current model-driver stack'}, "
        f"while the trade is framed around entry {_safe_float(idea.get('entry_price')):.2f}, "
        f"stop {_safe_float(idea.get('stop_loss')):.2f}, and target {_safe_float(idea.get('target_price')):.2f}."
    )
    if not settings.groq_api_key:
        return fallback

    checklist = idea.get("checklist") or {}
    checklist_lines = []
    for key, value in checklist.items():
        checklist_lines.append(
            f"- {key}: passed={bool(value.get('passed'))}, score={_safe_float(value.get('score')):.2f}, reason={value.get('reason', '')}"
        )

    messages = [
        {
            "role": "system",
            "content": (
                "You are explaining a trade idea inside an NSE portfolio research app. "
                "Write two compact paragraphs: thesis first, then risk framing. "
                "Use the supplied checklist reasons and keep it grounded in the numeric setup."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Trade idea: {json.dumps(idea, ensure_ascii=True)}\n"
                f"Checklist detail:\n{chr(10).join(checklist_lines)}\n"
                f"Portfolio context: {json.dumps(portfolio_context or {}, ensure_ascii=True)}"
            ),
        },
    ]
    completion = await _groq_completion(messages=messages, max_tokens=260, temperature=0.25)
    if completion:
        return completion
    return fallback


async def explain_backtest(backtest: dict[str, Any], portfolio_context: dict[str, Any] | None = None) -> str:
    fallback = (
        f"The latest replay finished at {_safe_float(backtest.get('final_value')):,.0f}, "
        f"for {_safe_float(backtest.get('total_return')):+.2f}% total return and "
        f"{_safe_float(backtest.get('cagr')):+.2f}% CAGR. "
        f"Risk came through {_safe_float(backtest.get('max_drawdown')):.2f}% max drawdown and "
        f"{_safe_float(backtest.get('sharpe')):.2f} Sharpe, "
        f"with {_safe_float(backtest.get('total_trades'), 0):.0f} trades over the period."
    )
    if not settings.groq_api_key:
        return fallback

    messages = [
        {
            "role": "system",
            "content": (
                "You are explaining a completed backtest in an NSE portfolio research app. "
                "Write two short paragraphs: performance interpretation first, then what the user should infer about risk, frictions, and robustness."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Backtest summary: {json.dumps(backtest, ensure_ascii=True)}\n"
                f"Portfolio context: {json.dumps(portfolio_context or {}, ensure_ascii=True)}"
            ),
        },
    ]
    completion = await _groq_completion(messages=messages, max_tokens=260, temperature=0.2)
    if completion:
        return completion
    return fallback
