
import os
import pyotp
import time
from SmartApi.smartConnect import SmartConnect
from SmartApi.smartWebSocketV2 import SmartWebSocketV2
from nse_token_data_cleaned import nse_tokens
from screener_scraper import get_fundamental_data
from flask import Flask

# Step 1: Load credentials
api_key = os.getenv("SMARTAPI_API_KEY")
client_code = os.getenv("SMARTAPI_CLIENT_CODE")
password = os.getenv("SMARTAPI_PASSWORD")
totp_secret = os.getenv("SMARTAPI_TOTP")

# Step 2: Generate TOTP
totp = pyotp.TOTP(totp_secret).now()

# Step 3: Login
print("Logging in...")
obj = SmartConnect(api_key=api_key)

try:
    session = obj.generateSession(client_code, password, totp)
    print("Login response:", session)
except Exception as e:
    print("Login failed:", e)
    exit()

jwt_token = session["data"]["jwtToken"]
feed_token = session["data"]["feedToken"]
print("Login successful.")

# Step 4: Extract symbols and tokens
symbols = [entry["symbol"] for entry in nse_tokens if "symbol" in entry]
token_ids = [int(entry["token"]) for entry in nse_tokens if "token" in entry]

# Step 5: Fetch fundamentals
print("Fetching fundamentals...")
fundamentals = get_fundamental_data(symbols)

# Step 6: Filter stocks
def filter_stocks(fundamentals):
    filtered = []
    for stock in fundamentals:
        try:
            roe = float(stock["roe"]) if stock["roe"] else 0
            eps = float(stock["eps_growth"]) if stock["eps_growth"] else 0
            if roe >= 15 and eps >= 20:
                filtered.append(stock)
        except Exception as e:
            print(f"Error in filtering {stock['symbol']}: {e}")
    return filtered

filtered_stocks = filter_stocks(fundamentals)
print("Filtered stocks:", filtered_stocks)

# Step 7: WebSocket setup
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

# Step 8: Start WebSocket
ss.connect()

# Step 9: Flask app for Render keep-alive
app = Flask(__name__)

@app.route("/")
def index():
    return "Alpha Bot is Live!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
