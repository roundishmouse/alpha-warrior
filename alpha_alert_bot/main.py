from SmartApi import SmartConnect
from SmartApi.smartWebSocketV2 import SmartWebSocketV2
import pyotp
import os
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

# Step 4: Prepare token list
tokens = [f"nse_cm|{stock['token']}" for stock in nse_tokens]
print(f"Subscribing to {len(tokens)} tokens")

# Step 5: Setup WebSocket
ss = SmartWebSocketV2(api_key, client_code, feed_token)

def on_data(wsapp, message):
    print("LIVE DATA:", message)

def on_open(wsapp):
    print("WebSocket opened. Sending subscription.")
    ss.subscribe(tokens)

def on_error(wsapp, error, reason):
    print("WebSocket Error:", error, reason)

def on_close(wsapp):
    print("WebSocket closed")

ss.on_data = on_data
ss.on_open = on_open
ss.on_error = on_error
ss.on_close = on_close

# Step 6: Connect WebSocket
ss.connect()
