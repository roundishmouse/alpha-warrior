import os
import time
import hmac
import base64
import struct
import hashlib
import requests
import json
import websocket
import threading
import pandas as pd
import pyotp

from smartapi.smartWebSocket import SmartWebSocket as WebSocket  # ✅ Import WebSocket properly

# Global Variables
session_data = {}
live_data = {}

# Custom TOTP generator
def generate_totp(secret):
    return pyotp.TOTP(secret).now()

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

# WebSocket Connection
def start_websocket():
    angel_login()  # Manual login instead of SmartConnect

    # Check if login was successful
    if not session_data or not all(k in session_data for k in ('feedToken', 'jwtToken', 'clientcode')):
        print("Login failed or session data missing")
        print(session_data)
        return

    feed_token = session_data['feedToken']
    jwt_token = session_data['jwtToken']
    client_code = session_data['clientcode']

    ws = WebSocket(feed_token, client_code, jwt_token)

    # Load tokens from file
    with open("token_list.txt", "r") as f:
        tokens = f.read().splitlines()

    def on_tick(ws, tick):
        global live_data
        print("Received Tick:", tick)
        # You can also update live_data here if needed

    def on_connect(ws, response):
        print("✅ WebSocket connection opened")
        ws.subscribe(tokens)

    ws.on_ticks = on_tick
    ws.on_connect = on_connect
    ws.connect()

# Top Stocks Analysis
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
    df['volume_spike'] = df['volume'] / df['open']  # Volume spike (open price fallback)
    df = df[df['volume_spike'] >= 1.2]  # Minimum 20% spike in volume
    df['momentum'] = (df['ltp'] / df['open']) - 1  # Momentum score
    df['score'] = df['momentum'] * 100  # Final scoring

    top_stocks = df.sort_values(by='score', ascending=False).head(2)

    if top_stocks.empty:
        return [{"symbol": "No Picks Passed", "score": 0}]

    return top_stocks[['symbol', 'score']].to_dict(orient='records')
