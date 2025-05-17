from smartapi.smartConnect import SmartConnect
import os

# Environment Variables
api_key = os.getenv("SMARTAPI_API_KEY")
client_code = os.getenv("SMARTAPI_CLIENT_CODE")
password = os.getenv("SMARTAPI_PASSWORD")
pin = os.getenv("SMARTAPI_PIN")

# Initialize SmartConnect
obj = SmartConnect(api_key)

# Perform login
try:
    data = obj.generateSession(client_code, password, pin)
    print("Login successful!")
    print("JWT Token:", data['data']['jwtToken'])
except Exception as e:
    print("Login failed:", e)
