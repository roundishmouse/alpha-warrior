from smartapi import SmartConnect
import os
import pyotp

api_key = os.getenv("SMARTAPI_API_KEY")
client_code = os.getenv("SMARTAPI_CLIENT_CODE")
password = os.getenv("SMARTAPI_PASSWORD")
totp_secret = os.getenv("SMARTAPI_TOTP")

totp = pyotp.TOTP(totp_secret).now()
print("Generated TOTP:", totp)

obj = SmartConnect(api_key)

try:
    data = obj.generateSession(client_code, password, totp)
    print("Login successful!")
    print("JWT Token:", data['data']['jwtToken'])
except Exception as e:
    print("Login failed:", e)
