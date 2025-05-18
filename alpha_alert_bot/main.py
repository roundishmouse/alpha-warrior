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

# Environment variables
api_key = os.getenv("SMARTAPI_API_KEY")
client_code = os.getenv("SMARTAPI_CLIENT_CODE")
password = os.getenv("SMARTAPI_PASSWORD")
totp_secret = os.getenv("SMARTAPI_TOTP")
telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
telegram_chat_id = os.getenv("T_BOT_CHAT_ID")

# Step 1: Generate TOTP
totp = pyotp.TOTP(totp_secret).now()

# Step 2: Login
print("Logging in...")
obj = SmartConnect(api_key=api_key)
data = obj.generateSession(client_code, password, totp)
jwt_token = data["data"]["jwtToken"]
feed_token = data["data"]["feedToken"]
print("Login successful.")

# Step 3: Extract 50 symbols only for test
symbols = [entry["symbol"] for entry in nse_tokens[:50]]

# Step 4: Fetch fundamentals from Screener.in
print("Fetching fundamentals...")
fundamentals = get_fundamental_data(symbols)

# Step 5: Filter CANSLIM + Minervini (promoter holding skipped)
def filter_stocks(fundamentals):
    filtered = []
    for stock in fundamentals:
        try:
            roe = float(stock["roe"]) if stock["roe"] else 0
            eps = float(stock["eps_growth"]) if stock["eps_growth"] else 0
            high = float(stock["52w_high"]) if stock["52w_high"] else 0
            if roe >= 15 and eps >= 20:
                filtered.append(stock)
        except Exception as e:
            print(f"Error filtering {stock['symbol']}: {e}")
    return filtered

top_stocks = filter_stocks(fundamentals)
print("Filtered stocks:", top_stocks)

# Step 6: Send Telegram alert
def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
    payload = {"chat_id": telegram_chat_id, "text": message}
    try:
        r = requests.post(url, data=payload)
        print("Telegram alert sent.")
    except Exception as e:
        print("Error sending Telegram alert:", e)

message = "Top filtered stocks today:"
for stock in top_stocks:
    message += f"\n{stock['symbol']} - ROE: {stock['roe']}, EPS: {stock['eps_growth']}, High: {stock['52w_high']}"
send_telegram_alert(message)

# Step 7: Subscribe to token IDs via WebSocket
token_ids = [int(stock["token"]) for stock in nse_tokens[:50]]
ss = SmartWebSocketV2(auth_token=jwt_token, api_key=api_key, client_code=client_code, feed_token=feed_token)

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

# Bind handlers
ss.on_open = on_open
ss.on_data = on_data
ss.on_error = on_error
ss.on_close = on_close

# Flask server to keep Render service alive
app = Flask(__name__)

@app.route('/')
def index():
    return "Alpha Bot is Live!"

def run_flask():
    app.run(host="0.0.0.0", port=10000)

# Start Flask + WebSocket in parallel threads
flask_thread = threading.Thread(target=run_flask)
flask_thread.start()
ss.connect()
