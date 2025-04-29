import os
import time
import requests
from flask import Flask
from angel_one_api import start_websocket, get_top_stocks

app = Flask(__name__)

start_websocket()  # Start WebSocket as soon as server starts

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
T_BOT_CHAT_ID = os.environ.get('T_BOT_CHAT_ID')

@app.route('/')
def home():
    return "Alpha Warrior WebSocket Bot is Running!"

@app.route('/wakeup')
def wakeup():
    return "Woke Up! Preparing Scan..."

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": T_BOT_CHAT_ID,
        "text": message
    }
    requests.post(url, data=payload)

def scheduled_task():
    while True:
        current_time = time.strftime("%H:%M")
        if current_time >= "09:15" and current_time <= "09:20":
            top_stocks = get_top_stocks()

            message = "🚀 Alpha Warrior Live Picks 🚀\n"
            for stock in top_stocks:
                message += f"✅ {stock['symbol']} | Score: {stock['score']:.2f}\n"

            send_telegram_message(message)
            time.sleep(3600)  # Sleep for an hour after sending picks
        else:
            print(f"Waiting... {current_time}")
            time.sleep(30)

import threading
threading.Thread(target=scheduled_task).start()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=81)
