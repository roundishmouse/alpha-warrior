import json
import time
from screener_scraper import get_fundamental_data
from nse_token_data_cleaned import token_data
import requests
import os
from SmartApi.smartConnect import SmartConnect
from smartapi.smartWebSocketV2 import SmartWebSocketV2
from flask import Flask

app = Flask(__name__)

# Load environment variables
api_key = os.getenv("SMARTAPI_API_KEY")
client_code = os.getenv("SMARTAPI_CLIENT_CODE")
password = os.getenv("SMARTAPI_PASSWORD")
totp = os.getenv("SMARTAPI_TOTP")
telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
telegram_chat_id = os.getenv("T_BOT_CHAT_ID")

def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
    data = {"chat_id": telegram_chat_id, "text": message}
    requests.post(url, data=data)

def filter_stocks(fundamentals):
    filtered = []
    for stock in fundamentals:
        try:
            roe = float(stock["roe"]) if stock["roe"] else 0
            eps = float(stock["eps_growth"]) if stock["eps_growth"] else 0
            high = float(stock["52w_high"]) if stock["52w_high"] else 0

            if roe >= 15 and eps >= 20:
                filtered.append(stock)
        except Exception as e:
            print(f"Error in filtering {stock['symbol']}: {e}")
    return filtered

def main():
    print("Logging in...")
    obj = SmartConnect(api_key=api_key)
    session = obj.generateSession(client_code, password, totp)
    feed_token = session["data"]["feedToken"]
    print("Login successful.")

    print("Loading symbols from token list...")
    symbols = [entry["symbol"] for entry in token_data if not entry["symbol"].endswith("ETF")]

    print(f"Scanning {len(symbols)} stocks from Screener...")
    fundamentals = get_fundamental_data(symbols)

    print("Applying CANSLIM + Minervini filters...")
    final_stocks = filter_stocks(fundamentals)

    if final_stocks:
        message = "Top CANSLIM + Minervini Stocks Today:\n" + "\n".join(
            [f"{s['symbol']} | ROE: {s['roe']} | EPS: {s['eps_growth']} | 52W High: {s['52w_high']}" for s in final_stocks]
        )
    else:
        message = "No stocks passed CANSLIM + Minervini filters today."

    print(message)
    send_telegram_alert(message)

@app.route("/")
def home():
    return "Quant bot running."

if __name__ == "__main__":
    main()
    app.run(host="0.0.0.0", port=10000)
