import os
import json
import requests
import pandas as pd
from Smartapi.smartConnect import SmartConnect

session_data = {}

def angel_login():
    obj = SmartConnect(api_key=os.environ.get("SMARTAPI_API_KEY"))
    data = obj.generateSession(
        os.environ.get("SMARTAPI_CLIENT_CODE"),
        os.environ.get("SMARTAPI_PASSWORD"),
        os.environ.get("SMARTAPI_TOTP")
    )
    session_data["token"] = data["data"]["jwtToken"]
    session_data["clientcode"] = os.environ.get("SMARTAPI_CLIENT_CODE")
    return obj

def fetch_live_price(symbol_token, exchange="NSE"):
    url = "https://apiconnect.angelbroking.com/rest/secure/angelbroking/order/v1/getLtpData"
    headers = {
        "X-PrivateKey": os.environ.get("SMARTAPI_API_KEY"),
        "Accept": "application/json",
        "X-SourceID": "WEB",
        "X-ClientLocalIP": "127.0.0.1",
        "X-ClientPublicIP": "127.0.0.1",
        "X-MACAddress": "00:00:00:00:00:00",
        "X-UserType": "USER",
        "Authorization": f"Bearer {session_data['token']}"
    }
    payload = {
        "exchange": exchange,
        "tradingsymbol": symbol_token,
        "symboltoken": symbol_token
    }
    res = requests.post(url, headers=headers, json=payload)
    return float(res.json()["data"]["ltp"])

def get_top_stocks():
    df = pd.read_csv("nse_tokens.csv")
    df = df.head(2)  # top 2 stocks
    return df

def send_telegram(message):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("T_BOT_CHAT_ID")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
    requests.post(url, data=payload)

def start_websocket():
    obj = angel_login()
    df = get_top_stocks()

    messages = []
    for _, row in df.iterrows():
        try:
            price = fetch_live_price(row['token'])
            target = round(price * 1.2, 2)
            sl = round(price * 0.9, 2)
            msg = f"<b>{row['symbol']}</b>\nEntry: {price}\nTarget: {target}\nSL: {sl}"
            messages.append(msg)
        except Exception as e:
            messages.append(f"{row['symbol']} - Error: {str(e)}")

    final_message = "\n\n".join(messages)
    send_telegram(final_message)
