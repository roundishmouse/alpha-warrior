import os
from SmartApi import SmartConnect
import pyotp

# Read environment variables
API_KEY = os.environ.get("SMARTAPI_API_KEY")
CLIENT_CODE = os.environ.get("SMARTAPI_CLIENT_CODE")
PIN = os.environ.get("SMARTAPI_PIN")
TOTP_SECRET = os.environ.get("SMARTAPI_TOTP")

obj = SmartConnect(api_key=API_KEY)

def generate_totp(secret):
    return pyotp.TOTP(secret).now()

def angel_login():
    data = {
        "client_code": CLIENT_CODE,
        "password": PIN,
        "totp": generate_totp(TOTP_SECRET)
    }
    try:
        session = obj.generateSession(data["client_code"], data["password"], data["totp"])
        print("✅ Login successful!")
        print("Token:", session["data"]["jwtToken"])
        return session["data"]
    except Exception as e:
        print("❌ Login failed or session data missing")
        print(e)
        return {}

def start_websocket():
    session_data = angel_login()
    if not isinstance(session_data, dict):
        print("❌ Login failed: 'data' is not a dictionary")
        return
    # Continue with WebSocket if needed
