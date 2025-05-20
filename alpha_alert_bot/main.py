
import os
import time
import threading
from flask import Flask
import yfinance as yf
from SmartApi.smartConnect import SmartConnect
from SmartApi.smartWebSocketV2 import SmartWebSocketV2
from nse_token_data_cleaned import nse_tokens
import pyotp
import requests
from screener_scraper import fetch_fundamentals_threaded as get_fundamental_data

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

def hybrid_filters(stock):
    try:
        price = float(stock.get("price", 0))
        high_52 = float(stock.get("52w high", 0))
        sma150 = float(stock.get("SMA150", 0))
        sma50_vol = float(stock.get("50DMA Volume", 0))
        curr_vol = float(stock.get("Volume", 0))

        if (
            price > sma150 and
            price >= 0.9 * high_52 and
            curr_vol > sma50_vol
        ):
            return True
    except:
        pass
    return False

def fetch_technical_data(symbols):
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
            sma150 = hist["Close"].rolling(window=150).mean().iloc[-1]
            sma50_vol = hist["Volume"].rolling(window=50).mean().iloc[-1]
            current_vol = hist["Volume"].iloc[-1]

            data.append({
                "symbol": symbol,
                "price": round(current_price, 2),
                "52w high": round(high_52, 2),
                "SMA150": round(sma150, 2),
                "50DMA Volume": int(sma50_vol),
                "Volume": int(current_vol),
            })

            time.sleep(0.1)
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
        time.sleep(5)  # Wait for TOTP to be valid

        obj = SmartConnect(api_key=api_key)
        data = obj.generateSession(client_code, password, totp)
        jwt_token = data["data"]["jwtToken"]
        feed_token = data["data"]["feedToken"]
        print("Login successful.")

        symbols = [entry["symbol"] for entry in nse_tokens]
        fundamentals = fetch_technical_data(symbols)
        selected = [f["symbol"] for f in fundamentals if hybrid_filters(f)]

        print(f"Final picks: {selected}")
        for symbol in selected:
            send_telegram_alert(symbol)

    except Exception as e:
        print(f"Bot error: {e}")

if __name__ == "__main__":
    threading.Thread(target=run_bot).start()
    app.run(host="0.0.0.0", port=10000)
