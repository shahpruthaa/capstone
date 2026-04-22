import math

from app.db.session import SessionLocal
from app.schemas.portfolio import GeneratePortfolioRequest, UserMandate
from app.services.db_quant_engine import generate_portfolio


def test_generate_portfolio_invariants() -> None:
    db = SessionLocal()
    try:
        req = GeneratePortfolioRequest(
            capital_amount=500000.0,
            mandate=UserMandate(
                investment_horizon_weeks="4-8",
                preferred_num_positions=10,
                allow_small_caps=True,
                risk_attitude="balanced",
            ),
        )
        res = generate_portfolio(db, req)

        total_weight = sum(allocation.weight for allocation in res.allocations)
        assert abs(total_weight - 100.0) < 1e-6

        sector_weights: dict[str, float] = {}
        for allocation in res.allocations:
            sector_weights[allocation.sector] = sector_weights.get(allocation.sector, 0.0) + allocation.weight
        assert abs(sum(sector_weights.values()) - 100.0) < 1e-6

        total_invested = sum(allocation.recommended_amount for allocation in res.allocations)
        assert total_invested <= req.capital_amount

        assert res.metrics.estimated_volatility_pct >= 0
        assert 0 <= res.metrics.diversification_score <= 100
        assert math.isfinite(res.standard_metrics.sharpe_ratio)
    finally:
        db.close()
