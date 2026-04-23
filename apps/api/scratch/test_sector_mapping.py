
from app.services.db_quant_engine import intelligent_sector_mapping

def test_sector_mapping():
    test_cases = {
        'EGOLD': 'Commodity',
        'GOLDBEES': 'Gold',
        'LIQUIDBEES': 'Liquid',
        'LIQUID1': 'Liquid',
        'LIQUIDPLUS': 'Liquid',
        'CASHIETF': 'Liquid',
        'GROWWLIQID': 'Liquid',
        'AXISBPSETF': 'Liquid',
        'TMB': 'Banking',
        'ASIANPAINT': 'Consumer',
        'LT': 'Infra',
        'NATIONALUM': 'Materials',
        'HINDALCO': 'Materials',
        'RELIANCE': 'Energy',  # Assuming it's in DB or hits a default/heuristic
    }
    
    print("--- Sector Mapping Smoke Test ---")
    all_passed = True
    for symbol, expected in test_cases.items():
        # Passing None for existing sector to force the override logic
        actual = intelligent_sector_mapping(symbol, None)
        if actual == expected:
            print(f"✅ {symbol:12} -> {actual}")
        else:
            print(f"❌ {symbol:12} -> Expected {expected}, got {actual}")
            all_passed = False
            
    if all_passed:
        print("\nPASS: All critical tickers correctly routed.")
    else:
        print("\nFAIL: Some tickers are misrouted.")

if __name__ == "__main__":
    test_sector_mapping()
