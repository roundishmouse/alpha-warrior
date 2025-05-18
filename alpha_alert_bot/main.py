
import os
import time
import pyotp
from threading import Thread
from server import run_server
from SmartApi import SmartConnect
from SmartApi.smartWebSocketV2 import SmartWebSocketV2
from nse_token_data import nse_tokens

# Start Flask server in background to keep Render alive
Thread(target=run_server).start()

# Environment variables
api_key = os.getenv("SMARTAPI_API_KEY")
client_code = os.getenv("SMARTAPI_CLIENT_CODE")
pin = os.getenv("SMARTAPI_PASSWORD")
totp_secret = os.getenv("SMARTAPI_TOTP")

# Generate TOTP
totp = pyotp.TOTP(totp_secret).now()
print("Generated TOTP:", totp)

# Login
obj = SmartConnect(api_key=api_key)
data = obj.generateSession(client_code, pin, totp)
jwt_token = data["data"]["jwtToken"]
feed_token = data["data"]["feedToken"]
print("Login successful")

# WebSocket setup
live_prices = {}

def on_open(ws):
    tokens = [stock["token"] for stock in nse_tokens]
    print(f"Subscribing to {len(tokens)} tokens")
    ws.subscribe(tokens)

def on_ticks(ws, ticks):
    for tick in ticks:
        symbol = tick.get("symbol")
        ltp = tick.get("last_traded_price")
        if symbol and ltp:
            live_prices[symbol] = ltp
    print(f"Received {len(live_prices)} prices")

def on_error(ws, code, reason):
    print("WebSocket error:", code, reason)

def on_close(ws, code, reason):
    print("WebSocket closed")

sws = SmartWebSocketV2(api_key, client_code, jwt_token, feed_token)
sws.on_open = on_open
sws.on_ticks = on_ticks
sws.on_error = on_error
sws.on_close = on_close

# Connect and run WebSocket
sws.connect()
time.sleep(15)
sws.close()

# Placeholder: filter logic to be added next
print("Collected prices for", len(live_prices), "stocks")
# for symbol, price in live_prices.items():
#     print(symbol, price)
