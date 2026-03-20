from fastapi import APIRouter

from app.api.routes import analysis, backtests, benchmarks, health, market_data, portfolio


api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(portfolio.router, prefix="/api/v1/portfolio", tags=["portfolio"])
api_router.include_router(analysis.router, prefix="/api/v1/analysis", tags=["analysis"])
api_router.include_router(backtests.router, prefix="/api/v1/backtests", tags=["backtests"])
api_router.include_router(benchmarks.router, prefix="/api/v1/benchmarks", tags=["benchmarks"])
api_router.include_router(market_data.router, prefix="/api/v1/market-data", tags=["market-data"])
