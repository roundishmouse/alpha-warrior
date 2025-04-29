import os
import time
import hmac
import base64
import struct
import hashlib
import requests

# Global Variables
session_data = {}

# Custom TOTP generator
def generate_totp(secret):
    key = base64.b32decode(secret, True)
    msg = struct.pack(">Q", int(time.time()) // 30)
    h = hmac.new(key, msg, hashlib.sha1).digest()
    o = h[19] & 15
    token = (struct.unpack(">I", h[o:o+4])[0] & 0x7fffffff) % 1000000
    return str(token).zfill(6)

# Manual Login Function
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

    response = requests.post("https://apiconnect.angelbroking.com/rest/auth/angelbroking/user/v1/loginByPassword", json=payload, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        session_data = {
            "jwtToken": data['data']['jwtToken'],
            "feedToken": data['data']['feedToken'],
            "clientcode": data['data']['clientcode']
        }
        print("✅ Logged in successfully!")
    else:
        print("❌ Login failed:", response.text)
import json
import websocket
import threading

# Global dictionary to store live data
live_data = {}

def start_websocket():
    global session_data

    feed_token = session_data['feedToken']
    client_code = session_data['clientcode']

    ws_url = f"wss://smartapisocket.angelone.in/smart-stream?client_code={client_code}&feed_token={feed_token}"

    def on_open(ws):
        print("✅ WebSocket connection opened!")
        
        # Load tokens to subscribe
        tokens = []
        with open("token_list.txt", "r") as f:
            for line in f:
                tokens.append(line.strip())

        # Subscribe to tokens
        for token in tokens:
            subscribe_payload = {
                "action": 1,
                "params": {
                    "mode": "FULL",
                    "tokenList": [token]
                }
            }
            ws.send(json.dumps(subscribe_payload))
            print(f"✅ Subscribed to: {token}")

    def on_message(ws, message):
        global live_data

        data = json.loads(message)
        
        if data.get('data'):
            for stock in data['data']:
                symbol = stock.get('symbol', 'Unknown')
                live_data[symbol] = {
                    "ltp": stock.get('ltp', 0),
                    "volume": stock.get('volume', 0),
                    "high": stock.get('high', 0),
                    "open": stock.get('open', 1)  # Avoid division by zero
                }

    def on_error(ws, error):
        print(f"❌ WebSocket Error: {error}")

    def on_close(ws, close_status_code, close_msg):
        print("❌ WebSocket connection closed")

    ws = websocket.WebSocketApp(ws_url,
                                 on_open=on_open,
                                 on_message=on_message,
                                 on_error=on_error,
                                 on_close=on_close)
    
    # Start WebSocket in a new thread
    wst = threading.Thread(target=ws.run_forever)
    wst.start()
import pandas as pd

def get_top_stocks():
    global live_data

    if not live_data:
        return [{"symbol": "No Picks Yet", "score": 0}]

    df = pd.DataFrame.from_dict(live_data, orient='index')
    df = df.reset_index().rename(columns={'index': 'symbol'})

    # Apply Filters
    df = df[df['ltp'] > 100]  # Minimum price
    df['distance_from_high'] = 1 - (df['ltp'] / df['high'])
    df = df[df['distance_from_high'] <= 0.25]  # Within 25% of 52-week high
    df['volume_spike'] = df['volume'] / df['open']  # Volume spike (using open as fallback)
    df = df[df['volume_spike'] >= 1.2]  # Minimum 20% spike in volume
    df['momentum'] = (df['ltp'] / df['open']) - 1  # Momentum score
    df['score'] = df['momentum'] * 100  # Final scoring

    top_stocks = df.sort_values(by='score', ascending=False).head(2)

    if top_stocks.empty:
        return [{"symbol": "No Picks Passed", "score": 0}]

    return top_stocks[['symbol', 'score']].to_dict(orient='records')
