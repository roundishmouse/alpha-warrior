import pyotp
import time
import requests

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
        totp = pyotp.TOTP(totp_secret).now()

        payload = {
            "clientcode": client_code,
            "password": pin,
            "totp": totp
        }

        headers = {
            "Content-Type": "application/json",
            "X-Api-Key": self.api_key
        }

        url = "https://apiconnect.angelbroking.com/rest/auth/angelbroking/user/v1/loginByPassword"
        
        response = requests.post(url, json=payload, headers=headers)
        data = response.json()
        

        if response.status_code == 200 and data.get("status"):
            self.jwt_token = data["data"]["jwtToken"]
            self.feed_token = data["data"]["feedToken"]
            self.refresh_token = data["data"]["refreshToken"]
            self.session_expiry = time.time() + 7200
            return data["data"]
        else:
            raise Exception(f"Login failed: {data.get('message', 'Unknown error')}")

    def getJwtToken(self):
        return self.jwt_token

    def getFeedToken(self):
        return self.feed_token

    def getClientCode(self):
        return self.client_code
