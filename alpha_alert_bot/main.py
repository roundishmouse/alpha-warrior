import os
import pyotp
import threading
import json
from flask import Flask
from SmartApi.smartConnect import SmartConnect
from SmartApi.smartWebSocketV2 import SmartWebSocketV2
from screener_scraper import get_fundamental_data
from nse_token_data_cleaned import nse_tokens
import requests

# Step 1: Load credentials from environment
api_key = os.getenv("SMARTAPI_API_KEY")
client_code = os.getenv("SMARTAPI_CLIENT_CODE")
password = os.getenv("SMARTAPI_PASSWORD")
totp_secret = os.getenv("SMARTAPI_TOTP")
telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
telegram_chat_id = os.getenv("T_BOT_CHAT_ID")

# Step 2: Generate TOTP
totp = pyotp.TOTP(totp_secret).now()
print("Generated TOTP:", totp)

# Step 3: Login
print("Logging in...")
obj = SmartConnect(api_key=api_key)
session = obj.generateSession(client_code, password, totp)
print("Login response:", session)
jwt_token = session["data"]["jwtToken"]
feed_token = session["data"]["feedToken"]
print("Login successful.")

# Step 4: Load Symbols
symbols = [entry["symbol"] for entry in nse_tokens if entry.get("symbol")]

# Step 5: Fetch fundamentals
print("Fetching fundamentals...")
fundamentals = get_fundamental_data(symbols)

# Step 6: Apply CANSLIM + Minervini filter
def filter_stocks(fundamentals):
    filtered = []
    for stock in fundamentals:
        try:
            roe = float(stock["roe"]) if stock["roe"] else 0
            eps = float(stock["eps_growth"]) if stock["eps_growth"] else 0
            high = float(stock["52w_high"]) if stock["52w_high"] else 0
            if roe > 15 and eps >= 20:
                filtered.append(stock)
        except Exception as e:
            print(f"Error in filtering {stock['symbol']}: {e}")
    return filtered

filtered_stocks = filter_stocks(fundamentals)
print("Filtered stocks:", filtered_stocks)

# Step 7: Send Telegram Alert
def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
    payload = {"chat_id": telegram_chat_id, "text": message}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print("Telegram Error:", e)

if filtered_stocks:
    msg = "Top Stocks:\n" + "\n".join(s["symbol"] for s in filtered_stocks)
    send_telegram_alert(msg)

# Step 8: Prepare token list for WebSocket
token_ids = [int(stock["token"]) for stock in nse_tokens if stock["symbol"] in [s["symbol"] for s in filtered_stocks]]

# Step 9: Setup WebSocket
ss = SmartWebSocketV2(
    auth_token=jwt_token,
    api_key=api_key,
    client_code=client_code,
    feed_token=feed_token
)

def on_data(wsapp, message):
    print("LIVE DATA:", message)

def on_open(wsapp):
    print("WebSocket opened. Sending subscription.")
    ss.subscribe(
        mode="full",
        token_list=[{"exchangeType": 1, "tokens": token_ids}],
        correlation_id="alpha_bot_001"
    )

def on_error(wsapp, error, reason):
    print("WebSocket Error:", error, reason)

def on_close(wsapp):
    print("WebSocket closed")

ss.on_open = on_open
ss.on_data = on_data
ss.on_error = on_error
ss.on_close = on_close

# Step 10: Start WebSocket in a thread
threading.Thread(target=ss.connect).start()

# Step 11: Flask app for keep-alive
app = Flask(__name__)

@app.route("/")
def index():
    return "Alpha Bot is Live!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
