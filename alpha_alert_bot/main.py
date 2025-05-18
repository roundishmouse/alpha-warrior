import os
import pyotp
import threading
from flask import Flask
from SmartApi.smartConnect import SmartConnect
from SmartApi.smartWebSocketV2 import SmartWebSocketV2
from nse_token_data_cleaned import nse_tokens

# Step 1: Load credentials from environment
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
print("Login successful")

jwt_token = data["data"]["jwtToken"]
feed_token = data["data"]["feedToken"]
print("Feed token is:", feed_token)

# Step 4: Prepare token list
token_ids = [int(stock["token"]) for stock in nse_tokens]
print(f"Subscribing to {len(token_ids)} tokens")

# Step 5: Setup WebSocket
ss = SmartWebSocketV2(
    auth_token=jwt_token,
    api_key=api_key,
    client_code=client_code,
    feed_token=feed_token
)

# Handlers
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

# Start Flask in separate thread and run WebSocket
flask_thread = threading.Thread(target=run_flask)
flask_thread.start()

# Start WebSocket connection
ss.connect()
