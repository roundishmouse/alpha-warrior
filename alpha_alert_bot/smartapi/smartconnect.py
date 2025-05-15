import requests
import pyotp

class SmartConnect:
    def __init__(self, api_key):
        self.api_key = api_key
        self.jwt_token = None
        self.feed_token = None
        self.refresh_token = None

    def generateSession(self, client_code, pin, totp_secret):
        totp = pyotp.TOTP(totp_secret).now()
        payload = {
            "clientcode": client_code,
            "pin": pin,
            "totp": totp,
        }

        headers = {
            "Content-Type": "application/json",
            "X-Api-Key": self.api_key
        }

        url = "https://apiconnect.angelbroking.com/rest/auth/angelbroking/user/v1/loginByPassword"

        response = requests.post(url, json=payload, headers=headers)
        result = response.json()

        if result["status"] and "data" in result:
            data = result["data"]
            self.jwt_token = data["jwtToken"]
            self.feed_token = data["feedToken"]
            self.refresh_token = data["refreshToken"]
            return result
        else:
            raise Exception(f"Login failed: {result}")

    def get_ltp(self, exchange, tradingsymbol, symboltoken):
        url = "https://apiconnect.angelbroking.com/rest/market/v2/ltpData"
        headers = {
            "Authorization": f"Bearer {self.jwt_token}",
            "X-Api-Key": self.api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "mode": "LTP",
            "exchange": exchange,
            "tradingsymbol": tradingsymbol,
            "symboltoken": symboltoken
        }
        response = requests.post(url, json=payload, headers=headers)
        return response.json()
