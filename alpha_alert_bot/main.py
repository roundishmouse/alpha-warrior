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
telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
telegram_chat_id = os.getenv("T_BOT_CHAT_ID")

# Step 2: Generate TOTP
totp = pyotp.TOTP(totp_secret).now()

# Step 3: Login
obj = SmartConnect(api_key=api_key)
data = obj.generateSession(client_code, password, totp)
jwt_token = data["data"]["jwtToken"]
feed_token = data["data"]["feedToken"]

# Step 4: Load symbols (limit to 50 for testing)
symbols = [entry["symbol"] for entry in nse_tokens[:50]]

# Step 5: Fetch Screener data
fundamentals = get_fundamental_data(symbols)

# Step 6: Apply filters
def clean_numeric_value(val):
    import re
    if not val:
        return None
    val = val.replace(",", "").replace("−", "-")  # fix unicode minus
    matches = re.findall(r"[-+]?\d*\.?\d+", val)
    return float(matches[0]) if matches else None

def filter_stocks(fundamentals):
    filtered = []
    for stock in fundamentals:
        try:
            roe = clean_numeric_value(stock["roe"])
            eps = clean_numeric_value(stock["eps_growth"])
            high = clean_numeric_value(stock["52w_high"])
            if roe is not None and eps is not None and roe > 15 and eps > 20:
                filtered.append(stock)
        except Exception as e:
            print(f"Error filtering {stock['symbol']}: {e}")
    return filtered

filtered = filter_stocks(fundamentals)

# Step 7: Send Telegram alert
bot = Bot(token=telegram_token)
if filtered:
    message = "Top filtered stocks today:\n" + "\n".join([s["symbol"] for s in filtered])
else:
    message = "No stocks passed the filter today."
bot.send_message(chat_id=telegram_chat_id, text=message)

# Step 8: WebSocket
ss = SmartWebSocketV2(auth_token=jwt_token, api_key=api_key, client_code=client_code, feed_token=feed_token)
token_ids = [int(stock["token"]) for stock in nse_tokens[:50]]

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

# Step 9: Flask + WebSocket threading
app = Flask(__name__)
@app.route("/")
def index():
    return "Alpha Bot is Live!"

def run_flask():
    app.run(host="0.0.0.0", port=10000)

flask_thread = threading.Thread(target=run_flask)
flask_thread.start()

ss.connect()
