from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from statistics import mean

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.services.market_event_analyzer import analyze_market_events
from app.services.portfolio_rebalancing import analyze_portfolio_rebalancing

router = APIRouter()


class StockExplainRequest(BaseModel):
    symbol: str
    sector: str = "Unknown"
    score: float = 0.0
    lgb_score: float = 0.0
    lstm_score: float = 0.0
    death_risk: float = 0.0
    news_sentiment: float = 0.0
    drivers: list[str] = []
    technicals: dict = {}
    portfolio_context: str = ""


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []
    portfolio_context: dict = {}


class PortfolioExplainRequest(BaseModel):
    allocations: list[dict] = []
    risk_mode: str = "MODERATE"
    total_amount: float = 500000


def _build_platform_context(db: Session) -> dict:
    from app.ingestion.market_regime import build_market_regime_snapshot
    from app.services.db_quant_engine import get_effective_trade_date
    from app.services.decision_engine import DecisionEngine

    context: dict = {}
    try:
        as_of = get_effective_trade_date(db)
        context["as_of_date"] = str(as_of)
        regime = build_market_regime_snapshot(db, trade_date=as_of)
        if regime:
            context["market_regime"] = {
                "regime": regime["regime"],
                "confidence": regime["regime_confidence"],
                "nifty_level": regime["nifty_50_level"],
                "breadth_50": regime["stocks_above_50d_sma_pct"],
                "breadth_200": regime["stocks_above_200d_sma_pct"],
                "india_vix": regime["india_vix"],
                "sma50": regime["nifty_50d_sma"],
                "sma200": regime["nifty_200d_sma"],
            }
    except Exception as exc:
        context["market_regime"] = {"regime": "unknown", "error": str(exc)}

    try:
        engine = DecisionEngine(db)
        ideas = engine.generate_trade_ideas(regime_filter=True, min_checklist_score=6, max_ideas=5)
        context["top_trade_ideas"] = [
            {
                "symbol": idea.symbol,
                "sector": idea.sector,
                "checklist_score": idea.checklist_score,
                "expected_return_annual": round(idea.expected_return_annual, 4),
                "regime_alignment": idea.regime_alignment,
                "entry": idea.entry_price,
                "stop": idea.stop_loss,
                "target": idea.target_price,
                "rr_ratio": idea.risk_reward_ratio,
                "top_drivers": idea.top_drivers[:3],
            }
            for idea in ideas
        ]
    except Exception as exc:
        context["top_trade_ideas"] = []
        context["trade_ideas_error"] = str(exc)

    try:
        context["market_events_analysis"] = analyze_market_events()
    except Exception as exc:
        context["market_events_analysis"] = "Market events analysis temporarily unavailable."
        context["market_events_error"] = str(exc)

    return context


def _merge_context(live_context: dict, request_context: dict) -> dict:
    merged = dict(live_context)
    merged.update({k: v for k, v in request_context.items() if k != "portfolio"})
    if request_context.get("portfolio") is not None:
        merged["portfolio"] = request_context["portfolio"]
    return merged


def _match_stock_contexts(message: str, portfolio_context: dict, db: Session, limit: int = 3) -> list[dict]:
    from app.services.db_quant_engine import get_effective_trade_date, load_snapshots
    from app.ml.ensemble_alpha.predict import get_ensemble_alpha_predictor

    query = message.lower()
    portfolio_allocations = (portfolio_context.get("portfolio") or {}).get("allocations", []) or []
    portfolio_symbols = {str(item.get("stock", {}).get("symbol") or item.get("symbol") or "").upper(): item for item in portfolio_allocations}

    as_of_date = get_effective_trade_date(db)
    snapshots = load_snapshots(db, as_of_date=as_of_date, min_history=90)
    snapshot_by_symbol = {snapshot.symbol.upper(): snapshot for snapshot in snapshots}

    candidates: list[tuple[float, object]] = []
    for snapshot in snapshots:
        symbol = snapshot.symbol.upper()
        name = snapshot.name.lower()
        score = 0.0
        if symbol in portfolio_symbols:
            score += 2.0
        if symbol.lower() in query:
            score += 4.0
        if name in query:
            score += 4.0
        else:
            compact_name = re.sub(r"[^a-z0-9]+", " ", name).strip()
            if compact_name and compact_name in query:
                score += 3.0
        if symbol.lower().startswith(query.strip()):
            score += 2.5
        if query.strip() and query.strip() in name:
            score += 1.5
        if score > 0:
            candidates.append((score, snapshot))

    ordered = [snapshot for _, snapshot in sorted(candidates, key=lambda item: item[0], reverse=True)[:limit]]
    if not ordered:
        return []

    predictor = get_ensemble_alpha_predictor()
    pred_map, _ = predictor.predict(db, ordered, as_of_date)

    matched: list[dict] = []
    for snapshot in ordered:
        portfolio_item = portfolio_symbols.get(snapshot.symbol.upper())
        pred = pred_map.get(snapshot.symbol)
        matched.append(
            {
                "symbol": snapshot.symbol,
                "name": snapshot.name,
                "sector": snapshot.sector,
                "market_cap_bucket": snapshot.market_cap_bucket or "Unknown",
                "beta": round(snapshot.beta_proxy, 2),
                "annual_volatility_pct": round(snapshot.annual_volatility_pct, 1),
                "momentum_3m_pct": round(snapshot.momentum_3m_pct, 1),
                "momentum_6m_pct": round(snapshot.momentum_6m_pct, 1),
                "news_explanation": snapshot.news_explanation or "",
                "ensemble_21d_return_pct": round(float(pred.pred_21d_return) * 100.0, 1) if pred else None,
                "ensemble_annual_return_pct": round(float(pred.pred_annual_return) * 100.0, 1) if pred else None,
                "top_drivers": list(pred.top_drivers[:3]) if pred else [],
                "in_portfolio": portfolio_item is not None,
                "portfolio_weight": float(portfolio_item.get("weight") or 0.0) if portfolio_item else 0.0,
            }
        )
    return matched


def _format_stock_contexts(stock_contexts: list[dict]) -> str:
    if not stock_contexts:
        return ""
    lines = []
    for stock in stock_contexts:
        holding_text = (
            f", in portfolio at {stock['portfolio_weight']:.1f}%"
            if stock["in_portfolio"]
            else ", not currently in portfolio"
        )
        ensemble_text = (
            f", ensemble 21d {stock['ensemble_21d_return_pct']:+.1f}%, annualized {stock['ensemble_annual_return_pct']:+.1f}%"
            if stock["ensemble_21d_return_pct"] is not None and stock["ensemble_annual_return_pct"] is not None
            else ""
        )
        driver_text = f", drivers {', '.join(stock['top_drivers'])}" if stock["top_drivers"] else ""
        news_text = f", news {stock['news_explanation']}" if stock["news_explanation"] else ""
        lines.append(
            f"- {stock['symbol']} ({stock['name']}) in {stock['sector']}, beta {stock['beta']:.2f}, 3M {stock['momentum_3m_pct']:+.1f}%, "
            f"6M {stock['momentum_6m_pct']:+.1f}%, vol {stock['annual_volatility_pct']:.1f}%{holding_text}{ensemble_text}{driver_text}{news_text}"
        )
    return "\n".join(lines)


def _build_system_prompt(portfolio_context: dict, stock_contexts: list[dict]) -> str:
    regime = portfolio_context.get("market_regime", {})
    if regime and regime.get("regime") not in (None, "unknown"):
        regime_str = (
            f"{str(regime.get('regime', '?')).upper()} market, "
            f"confidence {float(regime.get('confidence') or 0):.0%}, "
            f"Nifty {regime.get('nifty_level', 'N/A')}, "
            f"50d SMA {regime.get('sma50', 'N/A')}, "
            f"200d SMA {regime.get('sma200', 'N/A')}, "
            f"VIX {regime.get('india_vix', 'N/A')}, "
            f"above 50d SMA {regime.get('breadth_50', 'N/A')}%, above 200d SMA {regime.get('breadth_200', 'N/A')}%"
        )
    else:
        regime_str = "Market regime data not yet available."

    portfolio = portfolio_context.get("portfolio")
    if portfolio:
        allocations = portfolio.get("allocations", [])
        mandate = portfolio.get("mandate", {})
        top_holdings = ", ".join(
            f"{allocation.get('symbol') or allocation.get('stock', {}).get('symbol')} {float(allocation.get('weight') or 0):.1f}%"
            for allocation in allocations[:8]
        )
        portfolio_str = (
            f"ACTIVE PORTFOLIO: {str(mandate.get('risk_attitude', '?')).replace('_', ' ')} mandate, "
            f"{mandate.get('investment_horizon_weeks', '?')} week horizon, "
            f"Rs{float(portfolio.get('capital_amount') or 0):,.0f} invested, {len(allocations)} positions.\n"
            f"Holdings: {top_holdings or 'none'}"
        )
    else:
        portfolio_str = "No portfolio has been generated yet in this session."

    ideas = portfolio_context.get("top_trade_ideas", [])
    if ideas:
        ideas_str = "TOP TRADE IDEAS:\n" + "\n".join(
            f"- {idea['symbol']} ({idea['sector']}) {idea['checklist_score']}/10, {idea['regime_alignment']}, "
            f"forecast {float(idea['expected_return_annual']) * 100:+.1f}%, entry {idea['entry']:.2f}, stop {idea['stop']:.2f}, target {idea['target']:.2f}, RR {idea['rr_ratio']:.1f}"
            for idea in ideas
        )
    else:
        ideas_str = "No trade ideas currently cleared the checklist threshold."

    market_events = portfolio_context.get("market_events_analysis", "")
    events_str = ""
    if market_events and market_events != "Market events analysis temporarily unavailable.":
        events_str = f"\nCURRENT MARKET EVENTS:\n{str(market_events)[:600]}"

    stock_str = _format_stock_contexts(stock_contexts)
    referenced_stock_str = f"\nREFERENCED STOCKS:\n{stock_str}" if stock_str else ""

    return f"""You are a senior NSE portfolio analyst AI with access to the user's live platform state.

MARKET STATE: {regime_str}

{portfolio_str}

{ideas_str}{events_str}{referenced_stock_str}

INSTRUCTIONS:
- Answer from the context above and reference specific stocks, sectors, and numbers when they exist.
- For portfolio questions, explain concentration, sector mix, ensemble signals, and regime fit.
- For stock questions, explain the stock directly, say whether it is in the current portfolio, and mention relevant drivers.
- If the user asks to open a tab or run an action, use the available tool call.
- Be direct and concise. Prefer 2 short paragraphs or less unless the user asks for more detail."""


def _infer_action(message: str, has_portfolio: bool) -> dict | None:
    normalized = message.lower()
    if "compare" in normalized or "benchmark" in normalized:
        return {"name": "benchmark_portfolio", "arguments": {}}
    if "trade idea" in normalized or "ideas" in normalized:
        return {"name": "navigate_to_tab", "arguments": {"tab_name": "IDEAS"}}
    if "backtest" in normalized:
        return {"name": "run_backtest", "arguments": {}}
    if "market event" in normalized or "events" in normalized:
        return {"name": "navigate_to_tab", "arguments": {"tab_name": "EVENTS"}}
    if "market" in normalized or "news" in normalized:
        return {"name": "navigate_to_tab", "arguments": {"tab_name": "MARKET"}}
    if has_portfolio and ("analyze" in normalized or "portfolio" in normalized and "why" not in normalized):
        return {"name": "analyze_portfolio", "arguments": {}}
    return None


def _build_chat_fallback_response(message: str, portfolio_context: dict, stock_contexts: list[dict]) -> str:
    normalized = message.lower()
    portfolio = portfolio_context.get("portfolio") or {}
    allocations = portfolio.get("allocations", []) or []
    regime = portfolio_context.get("market_regime") or {}
    top_trade_ideas = portfolio_context.get("top_trade_ideas") or []

    if stock_contexts:
        primary = stock_contexts[0]
        portfolio_note = (
            f"It is currently in the generated portfolio at {primary['portfolio_weight']:.1f}% weight. "
            if primary["in_portfolio"]
            else "It is not currently in the generated portfolio. "
        )
        ensemble_note = (
            f"The current ensemble score points to {primary['ensemble_21d_return_pct']:+.1f}% over 21 trading days and {primary['ensemble_annual_return_pct']:+.1f}% annualized. "
            if primary["ensemble_21d_return_pct"] is not None and primary["ensemble_annual_return_pct"] is not None
            else ""
        )
        driver_note = (
            f"Top model drivers are {', '.join(primary['top_drivers'])}. "
            if primary["top_drivers"]
            else ""
        )
        news_note = f"News context: {primary['news_explanation']}. " if primary["news_explanation"] else ""
        return (
            f"{primary['symbol']} ({primary['sector']}) has beta {primary['beta']:.2f}, 3-month momentum {primary['momentum_3m_pct']:+.1f}%, "
            f"6-month momentum {primary['momentum_6m_pct']:+.1f}%, and annualized volatility of {primary['annual_volatility_pct']:.1f}%. "
            f"{portfolio_note}{ensemble_note}{driver_note}{news_note}"
        ).strip()

    if allocations and ("portfolio" in normalized or "why" in normalized or "reason" in normalized):
        top_holdings = sorted(allocations, key=lambda allocation: float(allocation.get("weight") or 0), reverse=True)[:5]
        top_text = ", ".join(
            f"{allocation.get('symbol') or allocation.get('stock', {}).get('symbol')} {float(allocation.get('weight') or 0):.1f}%"
            for allocation in top_holdings
        )
        sector_totals: dict[str, float] = {}
        for allocation in allocations:
            sector = str(allocation.get("sector") or allocation.get("stock", {}).get("sector") or "Unknown")
            sector_totals[sector] = sector_totals.get(sector, 0.0) + float(allocation.get("weight") or 0.0)
        sector_text = ", ".join(
            f"{sector} {weight:.1f}%"
            for sector, weight in sorted(sector_totals.items(), key=lambda item: item[1], reverse=True)[:4]
        )
        return (
            f"The current portfolio is built around {str((portfolio.get('mandate') or {}).get('risk_attitude', 'balanced')).replace('_', ' ')} risk with "
            f"{len(allocations)} positions. The heaviest holdings are {top_text}, and sector exposure is led by {sector_text}. "
            f"That mix should be read against the current {str(regime.get('regime') or 'unknown')} regime and the top checklist names already surfacing in the platform."
        )

    if top_trade_ideas:
        best_idea = top_trade_ideas[0]
        return (
            f"The market backdrop is {str(regime.get('regime') or 'unknown')} with confidence {float(regime.get('confidence') or 0):.0%}. "
            f"One of the strongest current ideas is {best_idea['symbol']} in {best_idea['sector']}, scoring {best_idea['checklist_score']}/10 with "
            f"forecast {float(best_idea['expected_return_annual']) * 100:+.1f}% and RR {best_idea['rr_ratio']:.1f}."
        )

    return "I can answer from the live NSE platform context, but I need either a generated portfolio or a clearer stock name to reason from."


@router.get("/context")
async def get_platform_context(db: Session = Depends(get_db)) -> dict:
    return _build_platform_context(db)


@router.post("/stock")
async def explain_stock_endpoint(req: StockExplainRequest) -> dict:
    from app.services.groq_explainer import explain_stock

    explanation = explain_stock(
        symbol=req.symbol,
        sector=req.sector,
        score=req.score,
        lgb_score=req.lgb_score,
        lstm_score=req.lstm_score,
        death_risk=req.death_risk,
        news_sentiment=req.news_sentiment,
        drivers=req.drivers,
        technicals=req.technicals,
        portfolio_context=req.portfolio_context,
    )
    return {"symbol": req.symbol, "explanation": explanation}


@router.post("/chat")
async def chat_endpoint(req: ChatRequest, db: Session = Depends(get_db)) -> dict:
    live_context = _build_platform_context(db)
    merged_context = _merge_context(live_context, req.portfolio_context or {})
    stock_contexts = _match_stock_contexts(req.message, merged_context, db)
    system_prompt = _build_system_prompt(merged_context, stock_contexts)
    tools = [
        {
            "type": "function",
            "function": {
                "name": "navigate_to_tab",
                "description": "Navigate to a tab in the application.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "tab_name": {"type": "string", "enum": ["MARKET", "EVENTS", "PORTFOLIO", "IDEAS", "BACKTEST", "COMPARE"]}
                    },
                    "required": ["tab_name"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "generate_portfolio",
                "description": "Generate a new AI portfolio.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "capital": {"type": "number"},
                        "risk": {"type": "string", "enum": ["CONSERVATIVE", "MODERATE", "AGGRESSIVE"]}
                    },
                    "required": ["capital", "risk"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "benchmark_portfolio",
                "description": "Open the benchmark comparison view.",
                "parameters": {"type": "object", "properties": {}}
            }
        },
        {
            "type": "function",
            "function": {
                "name": "analyze_portfolio",
                "description": "Open the portfolio analysis view.",
                "parameters": {"type": "object", "properties": {}}
            }
        },
        {
            "type": "function",
            "function": {
                "name": "run_backtest",
                "description": "Open the backtest view and start a replay.",
                "parameters": {"type": "object", "properties": {}}
            }
        }
    ]

    if not settings.groq_api_key:
        return {
            "response": _build_chat_fallback_response(req.message, merged_context, stock_contexts),
            "action": _infer_action(req.message, bool((merged_context.get("portfolio") or {}).get("allocations"))),
        }

    messages = [{"role": "system", "content": system_prompt}]
    for item in req.history[-6:]:
        messages.append(item)
    messages.append({"role": "user", "content": req.message})

    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.groq_api_key}", "Content-Type": "application/json"},
                json={"model": settings.groq_model, "max_tokens": 700, "messages": messages, "temperature": 0.25, "tools": tools},
            )
        if response.status_code != 200:
            return {
                "response": _build_chat_fallback_response(req.message, merged_context, stock_contexts),
                "action": _infer_action(req.message, bool((merged_context.get("portfolio") or {}).get("allocations"))),
            }

        data = response.json()
        message = data["choices"][0]["message"]
        if message.get("tool_calls"):
            tool_call = message["tool_calls"][0]
            return {
                "response": (message.get("content") or f"Opening {tool_call['function']['name'].replace('_', ' ')}.").strip(),
                "action": {
                    "name": tool_call["function"]["name"],
                    "arguments": json.loads(tool_call["function"]["arguments"]),
                },
            }

        content = (message.get("content") or "").strip()
        if content:
            return {"response": content}
    except Exception:
        pass

    return {
        "response": _build_chat_fallback_response(req.message, merged_context, stock_contexts),
        "action": _infer_action(req.message, bool((merged_context.get("portfolio") or {}).get("allocations"))),
    }


@router.post("/portfolio")
async def explain_portfolio_endpoint(req: PortfolioExplainRequest) -> dict:
    from app.services.groq_explainer import explain_portfolio

    explanation = explain_portfolio(
        allocations=req.allocations,
        risk_mode=req.risk_mode,
        total_amount=req.total_amount,
    )
    return {"explanation": explanation}


@router.get("/market-events")
async def analyze_market_events_endpoint() -> dict:
    analysis = analyze_market_events()
    return {"analysis": analysis, "generated_at": datetime.now(timezone.utc).isoformat()}


@router.post("/portfolio/rebalance")
async def rebalance_portfolio_endpoint(
    req: PortfolioExplainRequest,
    db: Session = Depends(get_db)
) -> dict:
    analysis = analyze_portfolio_rebalancing(
        db=db,
        allocations=req.allocations,
        risk_profile=req.risk_mode,
        investment_horizon="6-12 months",
        total_value=req.total_amount
    )

    return {
        "overall_assessment": analysis.overall_assessment,
        "risk_adjustment": analysis.risk_adjustment,
        "timeline": analysis.timeline,
        "explanation": analysis.explanation,
        "recommendations": [
            {
                "action": rec.action,
                "symbol": rec.symbol,
                "current_weight": rec.current_weight,
                "target_weight": rec.target_weight,
                "rationale": rec.rationale,
                "urgency": rec.urgency,
                "expected_impact": rec.expected_impact
            }
            for rec in analysis.recommendations
        ]
    }
