
import os
import pyotp
import threading
import requests
from flask import Flask
from SmartApi.smartConnect import SmartConnect
from SmartApi.smartWebSocketV2 import SmartWebSocketV2
from screener_scraper import get_fundamental_data
from nse_token_data_cleaned import nse_tokens

# Telegram setup
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("T_BOT_CHAT_ID")
def send_telegram_alert(message):
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
        try:
            requests.post(url, data=data)
        except Exception as e:
            print("Telegram Error:", e)

# Clean number from screener text
def clean_numeric_value(val):
    if not val:
        return None
    val = val.replace(",", "").replace("%", "").replace("−", "-").strip()
    for part in val.split():
        try:
            return float(part)
        except:
            continue
    return None

# Filters: CANSLIM + Minervini (excluding promoter holding)
def filter_stocks(fundamentals):
    filtered = []
    for stock in fundamentals:
        try:
            roe = clean_numeric_value(stock.get("roe", "")) or 0
            eps = clean_numeric_value(stock.get("eps_growth", "")) or 0
            high = clean_numeric_value(stock.get("52w_high", "")) or 0

            if roe >= 15 and eps >= 20:
                filtered.append(stock)
        except Exception as e:
            print(f"Error filtering {stock['symbol']}: {e}")
    return filtered

# Load credentials
api_key = os.getenv("SMARTAPI_API_KEY")
client_code = os.getenv("SMARTAPI_CLIENT_CODE")
password = os.getenv("SMARTAPI_PASSWORD")
totp_secret = os.getenv("SMARTAPI_TOTP")

# Generate TOTP
totp = pyotp.TOTP(totp_secret).now()
print("Generated TOTP:", totp)

# Login
obj = SmartConnect(api_key=api_key)
data = obj.generateSession(client_code, password, totp)
print("Login response:", data)
jwt_token = data["data"]["jwtToken"]
feed_token = data["data"]["feedToken"]
print("Login successful.")

# Prepare token list (50 stocks only for testing)
symbols = [entry["symbol"] for entry in nse_tokens][:50]
token_ids = [int(entry["token"]) for entry in nse_tokens if entry["symbol"] in symbols]

# Fetch Screener data
print("Fetching fundamentals...")
fundamentals = get_fundamental_data(symbols)
filtered_stocks = filter_stocks(fundamentals)

# Send Telegram alert
if filtered_stocks:
    message = "Top filtered stocks today:
" + "
".join([f"{s['symbol']} | ROE: {s['roe']} | EPS: {s['eps_growth']}" for s in filtered_stocks])
else:
    message = "No filtered stocks found today."
send_telegram_alert(message)

# Start WebSocket
ss = SmartWebSocketV2(auth_token=jwt_token, api_key=api_key, client_code=client_code, feed_token=feed_token)
def on_data(wsapp, message):
    print("LIVE DATA:", message)
def on_open(wsapp):
    print("WebSocket opened. Sending subscription.")
    ss.subscribe(mode="full", token_list=[{"exchangeType": 1, "tokens": token_ids}], correlation_id="alpha_bot_001")
def on_error(wsapp, error, reason):
    print("WebSocket Error:", error, reason)
def on_close(wsapp):
    print("WebSocket closed")
ss.on_open = on_open
ss.on_data = on_data
ss.on_error = on_error
ss.on_close = on_close

# Flask server for Render keep-alive
app = Flask(__name__)
@app.route('/')
def index():
    return "Alpha Bot is Live!"
def run_flask():
    app.run(host="0.0.0.0", port=10000)

# Start Flask + WebSocket in threads
threading.Thread(target=run_flask).start()
threading.Thread(target=ss.connect).start()
