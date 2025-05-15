import pyotp
import time
import requests
import datetime

class SmartConnect:
    def __init__(self, api_key):
        self.api_key = api_key.strip()
        self.jwt_token = None
        self.feed_token = None
        self.refresh_token = None
        self.client_code = None
        self.session_expiry = None

    def generateSession(self, client_code, pin, totp_secret):
        self.client_code = client_code
        now = datetime.datetime.utcnow()
        totp = pyotp.TOTP(totp_secret)
        generated_totp = totp.at(now)

        print("System Time (UTC):", now)
        print("TOTP being used by bot:", generated_totp)


        payload = {
            "clientcode": client_code,
            "password": pin,
            "totp": generated_totp
        }

        headers = {
            "Content-Type": "application/json",
            "X-Api-Key": self.api_key
        }

        url = "https://apiconnect.angelbroking.com/rest/auth/angelbroking/user/v1/loginByPassword"

        response = requests.post(url, json=payload, headers=headers)
        data = response.json()
        print(">>> RESPONSE:", response.status_code, data)

        if response.status_code == 200 and data.get("status"):
            self.jwt_token = data["data"]["jwtToken"]
            self.feed_token = data["data"]["feedToken"]
            self.refresh_token = data["data"]["refreshToken"]
        else:
            raise Exception("Login failed:", data)
