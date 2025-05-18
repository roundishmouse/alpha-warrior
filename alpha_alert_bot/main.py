import os
import threading
import time
import datetime
import requests
import pyotp
from flask import Flask
from SmartApi.smartConnect import SmartConnect
from nse_token_data import nse_token
from screener_scraper import get_screener_data
from telegram import Bot

# Environment Variables
api_key = os.getenv("SMARTAPI_API_KEY")
client_code = os.getenv("SMARTAPI_CLIENT_CODE")
password = os.getenv("SMARTAPI_PASSWORD")
totp_key = os.getenv("SMARTAPI_TOTP")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
T_BOT_CHAT_ID = os.getenv("T_BOT_CHAT_ID")

# Telegram Bot
bot = Bot(token=TELEGRAM_BOT_TOKEN)

# TOTP
totp = pyotp.TOTP(totp_key).now()

# Login
obj = SmartConnect(api_key=api_key)
data = obj.generateSession(client_code, password, totp)
print("Login response:", data)

if data.get("status") is False:
    raise Exception("Login failed: " + str(data))

jwt_token = data["data"]["jwtToken"]
feed_token = data["data"]["feedToken"]
print("Login successful")

# Filtered stock list (first 50 for test)
limited_tokens = nse_token[:50]

# Screener Cache
screener_cache = {}

# CANSLIM + Minervini Filter
def passes_filters(stock_data):
    roe = float(stock_data.get("ROE", "0").replace("%", "").strip())
    eps_growth = float(stock_data.get("EPS growth", "0").replace("%", "").strip())
    result_status = stock_data.get("Result", "").lower()

    return (
        roe > 15 and
        eps_growth > 20 and
        "good" in result_status
    )

# Stock Scanner
def scan_stocks():
    matching_stocks = []
    for stock in limited_tokens:
        symbol = stock["symbol"]
        if symbol in screener_cache:
            data = screener_cache[symbol]
        else:
            try:
                data = get_screener_data(symbol)
                screener_cache[symbol] = data
            except Exception as e:
                print(f"Error fetching data for {symbol}: {e}")
                continue

        if passes_filters(data):
            matching_stocks.append(symbol)

    if matching_stocks:
        message = "Top filtered stocks today:
" + "\n".join(matching_stocks)
        bot.send_message(chat_id=T_BOT_CHAT_ID, text=message)
        print("Alert sent on Telegram")
    else:
        print("No stocks matched the filters.")

# Flask keep-alive
app = Flask(__name__)
@app.route('/')
def home():
    return "Bot is alive!"

def run_flask():
    app.run(host='0.0.0.0', port=10000)

# Start everything
if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()

    scan_stocks()
