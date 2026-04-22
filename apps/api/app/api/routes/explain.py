from __future__ import annotations
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from app.db.session import get_db
from app.services.market_event_analyzer import analyze_market_events
from app.services.portfolio_rebalancing import analyze_portfolio_rebalancing, RebalancingAnalysis

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

@router.get("/context")
async def get_platform_context(db: Session = Depends(get_db)) -> dict:
    from app.ingestion.market_regime import build_market_regime_snapshot
    from app.services.db_quant_engine import get_effective_trade_date
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
    except Exception as e:
        context["market_regime"] = {"regime": "unknown", "error": str(e)}
    try:
        from app.services.decision_engine import DecisionEngine
        engine = DecisionEngine(db)
        ideas = engine.generate_trade_ideas(regime_filter=True, min_checklist_score=6, max_ideas=5)
        context["top_trade_ideas"] = [
            {
                "symbol": i.symbol,
                "sector": i.sector,
                "checklist_score": i.checklist_score,
                "expected_return_annual": round(i.expected_return_annual, 4),
                "regime_alignment": i.regime_alignment,
                "entry": i.entry_price,
                "stop": i.stop_loss,
                "target": i.target_price,
                "rr_ratio": i.risk_reward_ratio,
                "top_drivers": i.top_drivers[:3],
            }
            for i in ideas
        ]
    except Exception as e:
        context["top_trade_ideas"] = []
        context["trade_ideas_error"] = str(e)
    try:
        from app.services.market_event_analyzer import analyze_market_events
        context["market_events_analysis"] = analyze_market_events()
    except Exception as e:
        context["market_events_analysis"] = "Market events analysis temporarily unavailable."
        context["market_events_error"] = str(e)
    return context

def _build_system_prompt(portfolio_context: dict) -> str:
    regime = portfolio_context.get("market_regime", {})
    if regime and regime.get("regime") not in (None, "unknown"):
        regime_str = (
            f"{regime.get('regime','?').upper()} market — "
            f"confidence {float(regime.get('confidence') or 0):.0%}, "
            f"Nifty {regime.get('nifty_level','N/A')}, "
            f"50d SMA {regime.get('sma50','N/A')}, "
            f"200d SMA {regime.get('sma200','N/A')}, "
            f"VIX {regime.get('india_vix','N/A')}, "
            f"stocks above 50d SMA: {regime.get('breadth_50','N/A')}%, "
            f"above 200d SMA: {regime.get('breadth_200','N/A')}%"
        )
    else:
        regime_str = "Market regime data not yet available."

    portfolio = portfolio_context.get("portfolio")
    if portfolio:
        allocs = portfolio.get("allocations", [])
        mandate = portfolio.get("mandate", {})
        top_holdings = ", ".join(
            f"{a.get('symbol')} {float(a.get('weight') or 0):.1f}%"
            + (f" [ML21d: {float(a['ml_pred_21d_return'])*100:+.1f}%]" if a.get("ml_pred_21d_return") is not None else "")
            + (f" [death_risk: {float(a['death_risk']):.2f}]" if a.get("death_risk") is not None else "")
            for a in allocs[:8]
        )
        portfolio_str = (
            f"ACTIVE PORTFOLIO: {str(mandate.get('risk_attitude','?')).replace('_',' ')} mandate, "
            f"{mandate.get('investment_horizon_weeks','?')} week horizon, "
            f"Rs{float(portfolio.get('capital_amount') or 0):,.0f} invested, "
            f"{len(allocs)} positions.\nHoldings: {top_holdings}"
        )
    else:
        portfolio_str = "No portfolio has been generated yet in this session."

    ideas = portfolio_context.get("top_trade_ideas", [])
    if ideas:
        ideas_str = "TOP TRADE IDEAS (10-point checklist):\n" + "\n".join(
            f"  - {i['symbol']} ({i['sector']}) {i['checklist_score']}/10, "
            f"{i['regime_alignment']}, forecast {float(i['expected_return_annual'])*100:+.1f}%, "
            f"entry {i['entry']:.2f}/stop {i['stop']:.2f}/target {i['target']:.2f}, RR {i['rr_ratio']:.1f}"
            for i in ideas
        )
    else:
        ideas_str = "No trade ideas currently cleared the checklist threshold."

    backtest = portfolio_context.get("last_backtest")
    backtest_str = ""
    if backtest:
        m = backtest.get("metrics", {})
        backtest_str = (
            f"\nLAST BACKTEST ({backtest.get('start_date')} to {backtest.get('end_date')}): "
            f"CAGR {float(m.get('cagr_pct') or 0):.1f}%, "
            f"Sharpe {float(m.get('sharpe_ratio') or 0):.2f}, "
            f"max drawdown {float(m.get('max_drawdown_pct') or 0):.1f}%, "
            f"win rate {float(m.get('win_rate_pct') or 0):.1f}%."
        )

    market_events = portfolio_context.get("market_events_analysis", "")
    events_str = ""
    if market_events and market_events != "Market events analysis temporarily unavailable.":
        events_str = f"\n\nCURRENT MARKET EVENTS ANALYSIS:\n{market_events[:500]}..."  # Truncate for prompt size

    return f"""You are a senior NSE portfolio analyst AI with full real-time access to the user's platform state.

MARKET STATE: {regime_str}

{portfolio_str}

{ideas_str}{backtest_str}{events_str}

INSTRUCTIONS:
- Always reason from the context above. Reference specific stocks, sectors, and numbers.
- In a BEAR regime: emphasise capital preservation, quality, low beta. Flag high death_risk stocks.
- For portfolio questions: comment on concentration, sector exposure, ML signals, and regime fit.
- For trade idea questions: reference checklist scores and entry/stop/target levels.
- For market event questions: reference the current news analysis and sector impacts.
- Be direct, quantitative, concise — max 3 paragraphs. No generic disclaimers.
- If asked about a stock not in the portfolio, reason from sector trend, regime, and factor context.
- If the user asks to perform an action (e.g., generate a portfolio, benchmark it, analyze holdings, run a backtest, analyze market events, or rebalance portfolio), use the available tools to execute the action autonomously."""

@router.post("/stock")
async def explain_stock_endpoint(req: StockExplainRequest) -> dict:
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
async def chat_endpoint(req: ChatRequest) -> dict:
    import httpx
    import json
    from app.core.config import settings
    if not settings.groq_api_key:
        return {"response": "AI unavailable — no API key configured."}
    system_prompt = _build_system_prompt(req.portfolio_context)
    messages = [{"role": "system", "content": system_prompt}]
    for h in req.history[-6:]:
        messages.append(h)
    messages.append({"role": "user", "content": req.message})
    tools = [
        {
            "type": "function",
            "function": {
                "name": "navigate_to_tab",
                "description": "Navigates the user to a specific tab in the application. Use this if the user asks to see a different section, such as the market overview, portfolio, trade ideas, backtest, or compare tab.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "tab_name": {"type": "string", "enum": ["MARKET", "PORTFOLIO", "IDEAS", "BACKTEST", "COMPARE"]}
                    },
                    "required": ["tab_name"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "generate_portfolio",
                "description": "Generates a new AI portfolio for the user based on capital amount and risk profile. Use this if the user asks you to create, build, or generate a portfolio.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "capital": {"type": "number", "description": "The capital amount in INR (e.g. 1000000 for 10 lakhs)"},
                        "risk": {"type": "string", "enum": ["CONSERVATIVE", "MODERATE", "AGGRESSIVE"], "description": "The risk profile."}
                    },
                    "required": ["capital", "risk"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "benchmark_portfolio",
                "description": "Navigates to the comparison view to benchmark the portfolio against market standards.",
                "parameters": {"type": "object", "properties": {}}
            }
        },
        {
            "type": "function",
            "function": {
                "name": "analyze_portfolio",
                "description": "Navigates to the portfolio analysis view to review current holdings.",
                "parameters": {"type": "object", "properties": {}}
            }
        },
        {
            "type": "function",
            "function": {
                "name": "run_backtest",
                "description": "Navigates to the backtest tab and automatically starts a historical replay simulation.",
                "parameters": {"type": "object", "properties": {}}
            }
        },
        {
            "type": "function",
            "function": {
                "name": "analyze_market_events",
                "description": "Analyzes current market news and events for investment implications and trading opportunities.",
                "parameters": {"type": "object", "properties": {}}
            }
        },
        {
            "type": "function",
            "function": {
                "name": "rebalance_portfolio",
                "description": "Analyzes current portfolio and provides detailed rebalancing recommendations with explanations.",
                "parameters": {"type": "object", "properties": {}}
            }
        }
    ]

    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            r = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.groq_api_key}", "Content-Type": "application/json"},
                json={"model": settings.groq_model, "max_tokens": 600, "messages": messages, "temperature": 0.35, "tools": tools},
            )
            if r.status_code == 200:
                data = r.json()
                msg = data["choices"][0]["message"]
                
                # Check for tool calls
                if msg.get("tool_calls") and len(msg["tool_calls"]) > 0:
                    tool_call = msg["tool_calls"][0]
                    args = json.loads(tool_call["function"]["arguments"])
                    name = tool_call["function"]["name"]
                    return {
                        "response": f"Executing action: {name.replace('_', ' ')}...",
                        "action": {
                            "name": name,
                            "arguments": args
                        }
                    }
                
                content = msg.get("content")
                if content:
                    return {"response": content.strip()}
                return {"response": "Done."}
            return {"response": f"AI temporarily unavailable (status {r.status_code})."}
    except Exception:
        return {"response": "AI temporarily unavailable."}

class PortfolioExplainRequest(BaseModel):
    allocations: list[dict] = []
    risk_mode: str = "MODERATE"
    total_amount: float = 500000

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
    """Analyze current market events and news for investment implications."""
    analysis = analyze_market_events()
    return {"analysis": analysis, "generated_at": datetime.now(timezone.utc).isoformat()}

@router.post("/portfolio/rebalance")
async def rebalance_portfolio_endpoint(
    req: PortfolioExplainRequest,
    db: Session = Depends(get_db)
) -> dict:
    """Analyze portfolio and provide rebalancing recommendations."""
    analysis = analyze_portfolio_rebalancing(
        db=db,
        allocations=req.allocations,
        risk_profile=req.risk_mode,
        investment_horizon="6-12 months",  # Could be made configurable
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
