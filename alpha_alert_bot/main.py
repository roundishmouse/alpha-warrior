from smartapi.smartConnect import SmartConnect
import pyotp
import os

# Environment Variables (make sure these are set on Render)
api_key = os.getenv("SMARTAPI_API_KEY")
client_code = os.getenv("SMARTAPI_CLIENT_CODE")
password = os.getenv("SMARTAPI_PASSWORD")
totp_secret = os.getenv("SMARTAPI_TOTP")

# Generate TOTP
totp = pyotp.TOTP(totp_secret).now()
print("Generated TOTP:", totp)

# Initialize SmartConnect
obj = SmartConnect(api_key)

# Perform login with positional arguments
try:
    data = obj.generateSession(clientCode=client_code, password=password, totp_secret=totp)
    print("Login successful!")
    print("JWT Token:", data['data']['jwtToken'])
except Exception as e:
    print("Login failed:", e)
