import os
import time
import math
import threading
from flask import Flask
from SmartApi.smartConnect import SmartConnect
from SmartApi.smartWebSocketV2 import SmartWebSocketV2
from nse_token_data_cleaned import nse_tokens
from screener_scraper import fetch_fundamentals_threaded as get_fundamental_data
import pyotp
import requests
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running."

def send_telegram_alert(symbol):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("T_BOT_CHAT_ID")
    message = f"ALERT: {symbol} matches criteria"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        requests.post(url, data={"chat_id": chat_id, "text": message})
    except Exception as e:
        print(f"Telegram error: {e}")

def safe_float(val):
    try:
        val = float(val)
        return 0 if math.isnan(val) else val
    except:
        return 0

def safe_int(val):
    try:
        val = int(float(val))
        return 0 if math.isnan(val) else val
    except:
        return 0

def hybrid_filters(stock):
    try:
        price = safe_float(stock.get("price"))
        high_52 = safe_float(stock.get("52w high"))
        sma50 = safe_float(stock.get("SMA50"))
        sma_vol = safe_float(stock.get("SOMA Volume"))
        curr_vol = safe_float(stock.get("Volume"))
        return price > sma50 and price > 0.9 * high_52 and curr_vol > sma_vol
    except:
        return False

def fetch_technical_data(symbols):
    import yfinance as yf
    data = []
    for symbol in symbols:
        try:
            yf_symbol = symbol if symbol.endswith(".NS") else symbol + ".NS"
            stock = yf.Ticker(yf_symbol)
            hist = stock.history(period="200d")
            if hist.empty:
                continue
            current_price = hist["Close"].iloc[-1]
            high_52 = hist["High"].rolling(window=252).max().iloc[-1]
            sma50 = hist["Close"].rolling(window=50).mean().iloc[-1]
            sma_vol = hist["Volume"].rolling(window=50).mean().iloc[-1]
            curr_vol = hist["Volume"].iloc[-1]
            data.append({
                "symbol": symbol,
                "price": round(current_price, 2),
                "52w high": round(high_52, 2),
                "SMA50": round(sma50, 2),
                "SOMA Volume": round(sma_vol, 2),
                "Volume": round(curr_vol, 2),
            })
        except Exception as e:
            print(f"Error fetching {symbol}: {e}")
    return data

def run_bot():
    try:
        print("Logging in to SmartAPI...")
        api_key = os.getenv("SMARTAPI_API_KEY")
        client_code = os.getenv("SMARTAPI_CLIENT_CODE")
        password = os.getenv("SMARTAPI_PASSWORD")
        totp_secret = os.getenv("SMARTAPI_TOTP")
        totp = pyotp.TOTP(totp_secret).now()
        time.sleep(5)

        obj = SmartConnect(api_key=api_key)
        data = obj.generateSession(client_code, password, totp)
        token = data["data"]["jwtToken"]
        print("Login successful.")

        symbols = [entry["symbol"] for entry in nse_tokens]
        tech = fetch_technical_data(symbols)
        fundamentals = get_fundamental_data(symbols)

        if not fundamentals:
            print("No fundamentals data received. Skipping scan.")
            return

        combined = []
        for f in fundamentals:
            match = next((t for t in tech if t["symbol"] == f["symbol"]), None)
            if match:
                match.update(f)
                combined.append(match)

        # Apply filters and score stocks
        filtered = [s for s in combined if hybrid_filters(s)]
        ranked = sorted(filtered, key=lambda x: (
            x["Volume"] * ((x["price"] / x["SMA50"]) + (x["price"] / x["52w high"]))
        ), reverse=True)

        top_stocks = ranked[:5]  # Send max 5 alerts if >=2 exist
        if len(top_stocks) >= 2:
            for stock in top_stocks:
                send_telegram_alert(stock["symbol"])
        else:
            print("Less than 2 qualifying stocks — no alert sent.")

    except Exception as e:
        print(f"Bot error: {e}")

if __name__ == "__main__":
    threading.Thread(target=run_bot).start()
    app.run(host="0.0.0.0", port=10000)
