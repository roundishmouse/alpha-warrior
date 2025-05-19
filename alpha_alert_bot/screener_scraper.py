import yfinance as yf
import time

def fetch_technical_data(symbols):
    data = []
    for symbol in symbols:
        try:
            yf_symbol = symbol if symbol.endswith(".NS") else symbol + ".NS"
            stock = yf.Ticker(yf_symbol)
            hist = stock.history(period="200d")

            print(f"{symbol} - History Empty? {hist.empty}")  # Debug log

            if hist.empty:
                continue

            current_price = hist['Close'].iloc[-1]
            high_52 = hist['High'].rolling(window=252).max().iloc[-1]
            sma150 = hist['Close'].rolling(window=150).mean().iloc[-1]
            sma50_vol = hist['Volume'].rolling(window=50).mean().iloc[-1]
            current_vol = hist['Volume'].iloc[-1]

            data.append({
                "symbol": symbol,
                "price": round(current_price, 2),
                "52w high": round(high_52, 2),
                "SMA150": round(sma150, 2),
                "50DMA Volume": int(sma50_vol),
                "Volume": int(current_vol),
            })

            time.sleep(2)  # Delay to avoid rate limits
        except Exception as e:
            print(f"Error fetching {symbol}: {e}")
    return data
