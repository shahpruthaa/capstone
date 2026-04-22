import sys
import os

from app.db.session import SessionLocal
from app.schemas.portfolio import GeneratePortfolioRequest, UserMandate
from app.services.db_quant_engine import generate_portfolio

def run_test():
    db = SessionLocal()
    
    print("--- TEST 1: INFEASIBLE MANDATE (Only Banking) ---")
    try:
        req = GeneratePortfolioRequest(
            capital_amount=500000.0,
            mandate=UserMandate(
                investment_horizon_weeks="4-8",
                max_portfolio_drawdown_pct=12.0,
                max_position_size_pct=12.5,
                preferred_num_positions=10,
                sector_inclusions=["Banking"], 
                sector_exclusions=[],
                allow_small_caps=False,
                risk_attitude="balanced",
            )
        )
        generate_portfolio(db, req)
        print("FAILURE: It succeeded, but it should have been blocked.")
    except Exception as e:
        print(f"SUCCESS: Caught infeasible mandate -> {e}")

    print("\n--- TEST 2: STANDARD MANDATE ---")
    try:
        req = GeneratePortfolioRequest(
            capital_amount=500000.0,
            mandate=UserMandate(
                investment_horizon_weeks="4-8",
                max_portfolio_drawdown_pct=12.0,
                max_position_size_pct=15.0,
                preferred_num_positions=10,
                sector_inclusions=[],
                sector_exclusions=[],
                allow_small_caps=False,
                risk_attitude="balanced",
            )
        )
        res = generate_portfolio(db, req)
        total_weight = sum(a.weight for a in res.allocations)
        print(f"Total Allocations: {len(res.allocations)}")
        print(f"Sum of Weights: {total_weight}%")
        
        sector_weights = {}
        for a in res.allocations:
            print(f" - {a.symbol} ({a.sector}): {a.weight}%")
            sector_weights[a.sector] = sector_weights.get(a.sector, 0.0) + a.weight
            
        print("\nSector Breakdown:")
        for s, w in sector_weights.items():
            print(f" - {s}: {w}%")
            
    except Exception as e:
        print(f"Failed standard mandate: {e}")

if __name__ == "__main__":
    run_test()
