import yfinance as yf

def get_live_price(symbol: str) -> float:
    # yfinance requires '.NS' for Indian National Stock Exchange tickers
    ticker = symbol if symbol.endswith(".NS") else f"{symbol}.NS"
    
    try:
        # Fetch live market data
        data = yf.Ticker(ticker)
        # fast_info is highly optimized and doesn't download massive historical frames
        current_price = data.fast_info['last_price']
        
        if current_price is None or current_price == 0:
            raise ValueError("No price found")
            
        return float(current_price)
    except Exception as e:
        print(f"Failed to fetch live price for {symbol}: {e}")
        return 0.0 # Or fallback to your PostgreSQL database here
