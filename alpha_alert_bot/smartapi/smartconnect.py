import pyotp

class SmartConnect:
    def __init__(self, api_key):
        self.api_key = api_key
        self.jwt_token = None
        self.feed_token = None
        self.refresh_token = None

    def generateSession(self, client_code, pin, totp_secret):
        totp = pyotp.TOTP(totp_secret).now()
        
        print(f"[DUMMY LOGIN] Logging in with: API_KEY={self.api_key}, CLIENT_CODE={client_code}, PIN={pin}, TOTP={totp}")
        
        self.jwt_token = "mocked_jwt_token"
        self.feed_token = "mocked_feed"
        self.refresh_token = "mocked_refresh"
        
        return {
            "data": {
                "jwtToken": self.jwt_token
            }
        }
