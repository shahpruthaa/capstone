from fastapi import APIRouter
from app.api.routes import analysis, backtests, benchmarks, health, market_data, models, portfolio, news, explain, stock_detail, trade_ideas

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(portfolio.router, prefix="/api/v1/portfolio", tags=["portfolio"])
api_router.include_router(analysis.router, prefix="/api/v1/analysis", tags=["analysis"])
api_router.include_router(backtests.router, prefix="/api/v1/backtests", tags=["backtests"])
api_router.include_router(benchmarks.router, prefix="/api/v1/benchmarks", tags=["benchmarks"])
api_router.include_router(market_data.router, prefix="/api/v1/market-data", tags=["market-data"])
api_router.include_router(models.router, prefix="/api/v1/models", tags=["models"])
api_router.include_router(news.router, prefix="/api/v1/news", tags=["news"])
api_router.include_router(explain.router, prefix="/api/v1/explain", tags=["explain"])
api_router.include_router(stock_detail.router, prefix="/api/v1/stock", tags=["stock"])
api_router.include_router(trade_ideas.router, prefix="/api/v1/trade-ideas", tags=["trade-ideas"])
