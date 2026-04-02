from __future__ import annotations
from fastapi import APIRouter
from app.services.news_intelligence import get_market_context

router = APIRouter()

@router.get("/market-context")
async def market_context() -> dict:
    """Fetch and analyse current news for market impact on NSE sectors."""
    return await get_market_context()
