
from smartapi.smartConnect import SmartConnect
import pyotp
import requests
import os
from datetime import datetime

api_key = "CTtSQeSy"
client_code = "A505883"
password = "6130"
totp_secret = "3NO6IXIOTSDBEROL7QNWETWDEY"

# Step 1: Generate TOTP
totp = pyotp.TOTP(totp_secret).now()
print("Generated TOTP:", totp)

# Step 2: Create session
obj = SmartConnect(api_key=api_key)
data = obj.generateSession(clientCode=client_code, password=password, totp=totp)

# Step 3: Extract token
auth_token = data['data']['jwtToken']
print("Login Success. JWT Token:", auth_token)

# Step 4: Proceed with your stock strategy here
# This is where we will plug in Minervini + CANSLIM logic in next step
