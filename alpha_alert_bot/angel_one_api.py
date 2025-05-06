import os
import pandas as pd
from SmartApi import SmartConnect
import json

def start_websocket():
    print("⏳ Logging into Angel One...")
    obj = SmartConnect(api_key=os.getenv("SMARTAPI_KEY"))
    data = obj.generateSession(os.getenv("SMARTAPI_CLIENT"), os.getenv("SMARTAPI_PASSWORD"), os.getenv("SMARTAPI_TOTP"))
    feedToken = obj.getfeedToken()
    print("✅ Login successful")

    instruments = pd.read_csv("nse_tokens.csv")
    print(f"Loaded {len(instruments)} tokens.")

    top_stocks = instruments.head(2)
    print("Top 2 Stocks:", top_stocks[['symbol', 'token']].to_dict(orient='records'))
