import os
import requests
import json
import websocket
import threading
import pandas as pd
import pyotp

# Global Variables
session_data = {}
live_data = {}

# Generate TOTP from secret
def generate_totp(secret):
    return pyotp.TOTP(secret).now()

# AngelOne Login with error handling
def angel_login():
    global session_data

    payload = {
        "clientcode": os.environ.get('SMARTAPI_CLIENT'),
        "password": os.environ.get('SMARTAPI_PASSWORD'),
        "totp": generate_totp(os.environ.get('SMARTAPI_TOTP')),
    }

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Api-Key": os.environ.get('SMARTAPI_KEY'),
    }

    print("⏳ Sending login request...")
    response = requests.post(
        "https://apiconnect.angelbroking.com/rest/auth/angelbroking/user/v1/loginByPassword",
        json=payload,
        headers=headers
    )

    try:
        data = response.json()
        print("📦 Response JSON:", data)
    except Exception as e:
        print("❌ Failed to parse JSON:", e)
        print("Response Text:", response.text)
        return

    if not isinstance(data, dict):
        print("❌ Response is not a dictionary")
        return

    token_data = data.get('data')
    if not isinstance(token_data, dict):
        print("❌ Login failed: 'data' is not a dictionary")
        print("Data content:", token_data)
        return

    try:
        session_data = {
            "jwtToken": token_data['jwtToken'],
            "feedToken": token_data['feedToken'],
            "clientcode": token_data['clientcode']
        }
        print("✅ Logged in successfully!")
    except Exception as e:
        print("❌ Failed to extract token details:", e)
        print("Raw token_data:", token_data)
        return

# WebSocket Client for Tick Data
class AngelOneWebSocket:
    def __init__(self, feed_token, client_code):
        self.feed_token = feed_token
        self.client_code = client_code
        self.socket_opened = False

    def on_open(self, ws):
        print("✅ WebSocket opened")
        self.socket_opened = True
        self.subscribe_tokens(ws)

    def on_message(self, ws, message):
        global live_data
        print("Received Tick:", message)
        # You can parse and store ticks into live_data here if needed

    def on_error(self, ws, error):
        print("WebSocket Error:", error)

    def on_close(self, ws):
        print("❌ WebSocket closed")

    def subscribe_tokens(self, ws):
        with open("token_list.txt", "r") as f:
            tokens = f.read().splitlines()

        for token in tokens:
            data = {
                "task": "subscribe",
                "channel": token,
                "token": self.feed_token,
                "user": self.client_code
            }
            ws.send(json.dumps(data))
            print(f"Subscribed: {token}")

    def connect(self):
        websocket_url = "wss://smartapisocket.angelone.in/smart-stream"
        ws = websocket.WebSocketApp(websocket_url,
                                    on_open=self.on_open,
                                    on_message=self.on_message,
                                    on_error=self.on_error,
                                    on_close=self.on_close)

        wst = threading.Thread(target=ws.run_forever)
        wst.daemon = True
        wst.start()

# Function to start login and connect to WebSocket
def start_websocket():
    angel_login()

    if not session_data or not all(k in session_data for k in ('feedToken', 'jwtToken', 'clientcode')):
        print("Login failed or session data missing")
        print(session_data)
        return

    feed_token = session_data['feedToken']
    client_code = session_data['clientcode']
    ws = AngelOneWebSocket(feed_token, client_code)
    ws.connect()

# Ranking function for top stocks
def get_top_stocks():
    global live_data

    if not live_data:
        return [{"symbol": "No Picks Yet", "score": 0}]

    df = pd.DataFrame.from_dict(live_data, orient='index')
    df = df.reset_index().rename(columns={'index': 'symbol'})

    df = df[df['ltp'] > 100]
    df['distance_from_high'] = 1 - (df['ltp'] / df['high'])
    df = df[df['distance_from_high'] <= 0.25]
    df['volume_spike'] = df['volume'] / df['open']
    df = df[df['volume_spike'] >= 1.2]
    df['momentum'] = (df['ltp'] / df['open']) - 1
    df['score'] = df['momentum'] * 100

    top_stocks = df.sort_values(by='score', ascending=False).head(2)

    if top_stocks.empty:
        return [{"symbol": "No Picks Passed", "score": 0}]

    return top_stocks[['symbol', 'score']].to_dict(orient='records')
