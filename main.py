from flask import Flask
import os
import requests
from datetime import datetime, timedelta

app = Flask(__name__)

# Telegram Bot
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
T_BOT_CHAT_ID = os.environ.get('T_BOT_CHAT_ID')

def get_top_2_stock_picks():
    # Dummy picks (replace later with live model if needed)
    return [
        {"name": "TATAMOTORS", "score": 92.4},
        {"name": "CUMMINSIND", "score": 89.7},
    ]

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": T_BOT_CHAT_ID,
        "text": message
    }
    requests.post(url, data=payload)

@app.route('/')
def home():
    return "✅ Alpha Warrior 2.0 is LIVE and monitoring for 9:15 AM IST!"

@app.route('/test')
def test_message():
    message = "🧪 Test Ping from Alpha Warrior 2.0!"
    send_telegram(message)
    return "Test Message Sent"

@app.route('/run')
def scheduled_ping():
    now_ist = datetime.utcnow() + timedelta(hours=5, minutes=30)
    current_time = now_ist.strftime("%H:%M")
    
    if current_time == "09:15":
        stocks = get_top_2_stock_picks()
        message = "🚀 Quant Investing Alert\n"
        for i, stock in enumerate(stocks, 1):
            message += f"✅ Top Stock Pick {i}: {stock['name']} – Score: {stock['score']}\n"
        send_telegram(message)
        return "Alert Sent"
    else:
        return f"⏱️ Current IST time is {current_time} — waiting for 9:15 AM."

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=81)
