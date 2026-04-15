from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.groq_explainer import chat_with_assistant, explain_portfolio, explain_stock

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
    response = await chat_with_assistant(req.message, req.history)
    return {"response": response}


@router.post("/portfolio")
async def explain_portfolio_endpoint(req: PortfolioExplainRequest) -> dict:
    explanation = await explain_portfolio(
        allocations=req.allocations,
        risk_mode=req.risk_mode,
        total_amount=req.total_amount,
    )
    return {"explanation": explanation}
