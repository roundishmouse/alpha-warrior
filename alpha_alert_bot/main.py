from smartapi import SmartConnect
import pyotp
import os

# Environment variables
api_key = os.getenv("SMARTAPI_API_KEY")
client_code = os.getenv("SMARTAPI_CLIENT_CODE")
password = os.getenv("SMARTAPI_PASSWORD")
totp_secret = os.getenv("SMARTAPI_TOTP")

# Generate TOTP
totp = pyotp.TOTP(totp_secret).now()
print("Generated TOTP:", totp)

# Initialize SmartConnect
obj = SmartConnect(api_key=api_key)

# Login with only 3 args
try:
    data = obj.generateSession(client_code, password, totp)  # Only 3 args
    print("Login successful!")
    print("JWT Token:", data['data']['jwtToken'])
except Exception as e:
    print("Login failed:", e)
