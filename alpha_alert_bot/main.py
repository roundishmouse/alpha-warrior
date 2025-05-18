import os
import pyotp
import threading
from flask import Flask
from SmartApi.smartConnect import SmartConnect
from SmartApi.smartWebSocketV2 import SmartWebSocketV2
from screener_scraper import get_fundamental_data
from nse_token_data_cleaned import nse_tokens

# Step 1: Load credentials
api_key = os.getenv("SMARTAPI_API_KEY")
client_code = os.getenv("SMARTAPI_CLIENT_CODE")
password = os.getenv("SMARTAPI_PASSWORD")
totp_secret = os.getenv("SMARTAPI_TOTP")

# Step 2: Generate TOTP
totp = pyotp.TOTP(totp_secret).now()
print("Generated TOTP:", totp)

# Step 3: Login
obj = SmartConnect(api_key=api_key)
data = obj.generateSession(client_code, password, totp)
print("Login response:", data)
jwt_token = data["data"]["jwtToken"]
feed_token = data["data"]["feedToken"]
print("Login successful")

# Step 4: Load symbols
symbols = [entry["symbol"] for entry in nse_tokens if entry.get("symbol")]

# Step 5: Screener data
fundamentals = get_fundamental_data(symbols)

# Step 6: Filtering
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
            print(f"Error in filtering {stock['symbol']}: {e}")
    return filtered

top_fundamentals = filter_stocks(fundamentals)
print(f"Filtered {len(top_fundamentals)} stocks")

# Step 7: Prepare tokens
token_ids = [int(entry["token"]) for entry in token_data if entry.get("symbol")]

# Step 8: WebSocket Setup
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

# Step 9: Run WebSocket in a thread
threading.Thread(target=ss.connect).start()

# Step 10: Flask app for Render keep-alive
app = Flask(__name__)

@app.route("/")
def index():
    return "Alpha Bot is Live!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
