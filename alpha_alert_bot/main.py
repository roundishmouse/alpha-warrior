import os
import time
import math
import threading
from flask import Flask
from SmartApi.smartConnect import SmartConnect
import pyotp
import requests
import yfinance as yf
from nse_token_data_cleaned import nse_tokens
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running."

def send_telegram_alert(symbol):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("T_BOT_CHAT_ID")
    message = f"ALERT: {symbol} matches hybrid filter criteria"
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

def hybrid_filters(stock):
    try:
        price = safe_float(stock.get("price"))
        high_52 = safe_float(stock.get("52w high"))
        sma150 = safe_float(stock.get("SMA150"))
        sma_vol = safe_float(stock.get("SOMA Volume"))
        curr_vol = safe_float(stock.get("Volume"))
        return (
            price > 0.75 * high_52 and
            price > sma150 and
            curr_vol > sma_vol
        )
    except:
        return False

def fetch_technical_data(symbols):
    data = []
    for idx, symbol in enumerate(symbols):
        try:
            print(f"Fetching {idx+1}/{len(symbols)}: {symbol}")
            yf_symbol = symbol if symbol.endswith(".NS") else symbol + ".NS"
            stock = yf.Ticker(yf_symbol)
            hist = stock.history(period="300d")
            if hist.empty:
                continue
            current_price = hist["Close"].iloc[-1]
            high_52 = hist["High"].rolling(window=252).max().iloc[-1]
            sma150 = hist["Close"].rolling(window=150).mean().iloc[-1]
            sma_vol = hist["Volume"].rolling(window=50).mean().iloc[-1]
            curr_vol = hist["Volume"].iloc[-1]
            data.append({
                "symbol": symbol,
                "price": round(current_price, 2),
                "52w high": round(high_52, 2),
                "SMA150": round(sma150, 2),
                "SOMA Volume": round(sma_vol, 2),
                "Volume": round(curr_vol, 2),
            })
        except Exception as e:
            print(f"Error fetching {symbol}: {e}")
    return data

def is_market_bullish():
    try:
        nifty = yf.Ticker("^NSEI")
        hist = nifty.history(period="300d")
        if hist.empty:
            print("Failed to fetch Nifty data.")
            return False
        current = hist["Close"].iloc[-1]
        sma50 = hist["Close"].rolling(window=50).mean().iloc[-1]
        sma200 = hist["Close"].rolling(window=200).mean().iloc[-1]
        print(f"Nifty: {current}, SMA50: {sma50}, SMA200: {sma200}")
        return current > sma50 and current > sma200
    except Exception as e:
        print(f"Error checking market trend: {e}")
        return False

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

        if not is_market_bullish():
            print("Market is not bullish. Skipping scan.")
            return

        symbols = [entry["symbol"] for entry in nse_tokens]
        print(f"Scanning {len(symbols)} symbols...")

        tech_data = fetch_technical_data(symbols)
        print(f"Technical data fetched: {len(tech_data)}")

        filtered = [s for s in tech_data if hybrid_filters(s)]
        print(f"Stocks after hybrid filter: {len(filtered)}")

        if not filtered:
            print("No stocks matched today.")
            return

        ranked = sorted(filtered, key=lambda x: (
            x["Volume"] * ((x["price"] / x["SMA150"]) + (x["price"] / x["52w high"]))
        ), reverse=True)

        top_stocks = ranked[:5]
        for stock in top_stocks:
            send_telegram_alert(stock["symbol"])

    except Exception as e:
        print(f"Bot error: {e}")

if __name__ == "__main__":
    threading.Thread(target=run_bot).start()
    app.run(host="0.0.0.0", port=10000)
