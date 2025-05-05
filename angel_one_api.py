import os
import pyotp
from smartapi_python import SmartConnect

# Read environment variables
API_KEY = os.environ.get("SMARTAPI_API_KEY")
CLIENT_CODE = os.environ.get("SMARTAPI_CLIENT_CODE")
PIN = os.environ.get("SMARTAPI_PIN")
TOTP_SECRET = os.environ.get("SMARTAPI_TOTP")

obj = SmartConnect(api_key=API_KEY)

def generate_totp(secret):
    return pyotp.TOTP(secret).now()

def angel_login():
    try:
        totp = generate_totp(TOTP_SECRET)
        session = obj.generateSession(CLIENT_CODE, PIN, totp)
        print("✅ Login successful!")
        print("Token:", session["data"]["jwtToken"])
        return session["data"]
    except Exception as e:
        print("❌ Login failed")
        print(e)
        return {}

def start_websocket():
    session_data = angel_login()
    if not isinstance(session_data, dict) or "jwtToken" not in session_data:
        print("❌ Login failed or invalid token structure")
        return
    # You can expand this with WebSocket logic after successful login
