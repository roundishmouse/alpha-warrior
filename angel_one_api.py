import os
import time
import hmac
import base64
import struct
import hashlib
import pandas as pd
from smartapi import SmartConnect, WebSocket

# Global live data store
live_data = {}

# Custom TOTP generator (replaces pyotp)
def generate_totp(secret):
    key = base64.b32decode(secret, True)
    msg = struct.pack(">Q", int(time.time()) // 30)
    h = hmac.new(key, msg, hashlib.sha1).digest()
    o = h[19] & 15
    token = (struct.unpack(">I", h[o:o+4])[0] & 0x7fffffff) % 1000000
    return str(token).zfill(6)

# Angel One login
def angel_login():
    obj = SmartConnect(api_key=os.environ.get('SMARTAPI_KEY'))
    session_data = obj.generateSession(
        os.environ.get('SMARTAPI_CLIENT'),
        os.environ.get('SMARTAPI_PASSWORD'),
        generate_totp(os.environ.get('SMARTAPI_TOTP'))
    )
    return obj

# Start WebSocket for real-time data
def start_websocket():
    api_key = os.environ.get('SMARTAPI_KEY')
    client_code = os.environ.get('SMARTAPI_CLIENT')
    password = os.environ.get('SMARTAPI_PASSWORD')
    totp = generate_totp(os.environ.get('SMARTAPI_TOTP'))

    obj = SmartConnect(api_key=api_key)
    session_data = obj.generateSession(client_code, password, totp)

    feed_token = session_data['data']['feedToken']
    client_code = session_data['data']['clientcode']

    websocket = WebSocket(feed_token, client_code)

    # Token list (ensure token_list.txt is present)
    with open("token_list.txt", "r") as f:
        tokens = f.read().splitlines()

    def on_tick(ws, tick):
        global live_data
        symbol = tick['tradingsymbol']
        live_data[symbol] = {
            'ltp': tick['ltp'],
            'volume': tick['volume'],
            'high': tick['high_price'],
            'open': tick['open_price']
        }

    def on_connect(ws, response):
        ws.subscribe(tokens)

    websocket.on_ticks = on_tick
    websocket.on_connect = on_connect
    websocket.connect()

# Stock scoring & filtering logic
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
