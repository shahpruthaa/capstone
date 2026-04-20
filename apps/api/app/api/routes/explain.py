from __future__ import annotations
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db.session import get_db
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
    history: list[dict] = []
    portfolio_context: dict = {}

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
    from app.core.config import settings
    if not settings.groq_api_key:
        return {"response": "AI unavailable — no API key configured."}
    messages = [{"role": "system", "content": "You are an expert NSE trading assistant helping Indian investors understand AI-generated portfolio recommendations. Be concise, accurate, and reference specific stocks and sectors when relevant."}]
    for h in req.history[-6:]:
        messages.append(h)
    messages.append({"role": "user", "content": req.message})
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.groq_api_key}", "Content-Type": "application/json"},
                json={"model": settings.groq_model, "max_tokens": 500, "messages": messages, "temperature": 0.4},
            )
            if r.status_code == 200:
                return {"response": r.json()["choices"][0]["message"]["content"].strip()}
        return {"response": "AI temporarily unavailable."}
    except Exception as e:
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
