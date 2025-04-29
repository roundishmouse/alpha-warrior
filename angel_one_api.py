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
import pyotp

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
import json
import websocket
import threading

# Global dictionary to store live data
live_data = {}

def start_websocket():
  angel_login()  # manually logs in and sets global session_data

# Add this check to prevent crash
if not session_data or not all(k in session_data for k in ('feedToken', 'jwtToken', 'clientcode')):
    print("Login failed or session data missing")
    print(session_data)
    return


    feed_token = session_data['data']['feedToken']
    jwt_token = session_data['data']['jwtToken']
    client_code = session_data['data']['clientcode']

    websocket = WebSocket(feed_token, client_code, jwt_token)

    # Load tokens
    with open("token_list.txt", "r") as f:
        tokens = f.read().splitlines()

    def on_tick(ws, tick):
        global live_data
        # your logic here

    def on_connect(ws, response):
        ws.subscribe(tokens)

    websocket.on_ticks = on_tick
    websocket.on_connect = on_connect
    websocket.connect()

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
