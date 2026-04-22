import sys
import os

from app.db.session import SessionLocal
from app.schemas.portfolio import GeneratePortfolioRequest, UserMandate
from app.services.db_quant_engine import generate_portfolio

def run_test():
    db = SessionLocal()
    
    print("--- TEST 1: STANDARD ENSEMBLE MANDATE ---")
    try:
        req = GeneratePortfolioRequest(
            capital_amount=500000.0,
            mandate=UserMandate(
                investment_horizon_weeks="4-8",
                preferred_num_positions=10,
                allow_small_caps=False,
                risk_attitude="balanced",
            )
        )
        res = generate_portfolio(db, req)
        print(f"SUCCESS: Generated {len(res.allocations)} allocations.")
    except Exception as e:
        print(f"FAILURE: Unexpected generation error -> {e}")

    print("\n--- TEST 2: SMALL-CAP ENABLED MANDATE ---")
    try:
        req = GeneratePortfolioRequest(
            capital_amount=500000.0,
            mandate=UserMandate(
                investment_horizon_weeks="4-8",
                preferred_num_positions=10,
                allow_small_caps=True,
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
