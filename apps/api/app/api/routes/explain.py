from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.ai_assistant import chat_with_copilot, explain_backtest, explain_trade_idea
from app.services.groq_explainer import explain_stock, explain_portfolio

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
    history: list[dict[str, Any]] = Field(default_factory=list)
    grounded_context: dict[str, Any] = Field(default_factory=dict)

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
    return await chat_with_copilot(
        message=req.message,
        history=req.history,
        grounded_context=req.grounded_context,
    )

class PortfolioExplainRequest(BaseModel):
    allocations: list[dict] = Field(default_factory=list)
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


class TradeIdeaExplainRequest(BaseModel):
    idea: dict[str, Any] = Field(default_factory=dict)
    portfolio_context: dict[str, Any] = Field(default_factory=dict)


@router.post("/trade-idea")
async def explain_trade_idea_endpoint(req: TradeIdeaExplainRequest) -> dict:
    explanation = await explain_trade_idea(req.idea, req.portfolio_context)
    return {"explanation": explanation}


class BacktestExplainRequest(BaseModel):
    result: dict[str, Any] = Field(default_factory=dict)
    portfolio_context: dict[str, Any] = Field(default_factory=dict)


@router.post("/backtest")
async def explain_backtest_endpoint(req: BacktestExplainRequest) -> dict:
    explanation = await explain_backtest(req.result, req.portfolio_context)
    return {"explanation": explanation}
