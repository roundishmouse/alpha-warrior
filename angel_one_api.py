import os
import pandas as pd
import pyotp
from smartapi import SmartConnect
from smartapi import WebSocket

# Global Variables
live_data = {}

def angel_login():
    obj = SmartConnect(api_key=os.environ.get('SMARTAPI_KEY'))
    session_data = obj.generateSession(
        os.environ.get('SMARTAPI_CLIENT'),
        os.environ.get('SMARTAPI_PASSWORD'),
        pyotp.TOTP(os.environ.get('SMARTAPI_TOTP')).now()
    )
    return obj

def start_websocket():
    api_key = os.environ.get('SMARTAPI_KEY')
    client_code = os.environ.get('SMARTAPI_CLIENT')
    password = os.environ.get('SMARTAPI_PASSWORD')
    totp = pyotp.TOTP(os.environ.get('SMARTAPI_TOTP')).now()

    obj = SmartConnect(api_key=api_key)
    session_data = obj.generateSession(client_code, password, totp)

    feed_token = session_data['data']['feedToken']
    jwttoken = session_data['data']['jwtToken']
    client_code = session_data['data']['clientcode']

    websocket = WebSocket(feed_token, client_code)

    # List of Tokens you want to subscribe
    with open("token_list.txt", "r") as f:
        tokens = f.read().splitlines()

    # Callback functions
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

def get_top_stocks():
    global live_data
    if not live_data:
        return [{"symbol": "No Picks Yet", "score": 0}]

    df = pd.DataFrame.from_dict(live_data, orient='index')
    df = df.reset_index().rename(columns={'index': 'symbol'})

    # Apply Filters
    df = df[df['ltp'] > 100]
    df['distance_from_high'] = 1 - (df['ltp'] / df['high'])
    df = df[df['distance_from_high'] <= 0.25]
    df['volume_spike'] = df['volume'] / df['open']  # open is used as fallback for avg volume
    df = df[df['volume_spike'] >= 1.2]
    df['momentum'] = (df['ltp'] / df['open']) - 1
    df['score'] = df['momentum'] * 100

    top_stocks = df.sort_values(by='score', ascending=False).head(2)

    if top_stocks.empty:
        return [{"symbol": "No Picks Passed", "score": 0}]

    return top_stocks[['symbol', 'score']].to_dict(orient='records')
