from flask import Flask
import os
import requests
from datetime import datetime, timedelta

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
T_BOT_CHAT_ID = os.environ.get('T_BOT_CHAT_ID')

# Dummy top 2 picks — this can later be linked to your live quant model
def get_top_stock_picks():
    return [
        {"name": "TATAMOTORS", "score": 92.4},
        {"name": "CUMMINSIND", "score": 89.7}
    ]

@app.route('/')
def home():
    return "✅ Alpha Warrior Bot is up and watching for 9:15 AM IST"

@app.route('/test')
def send_test():
    message = "🔥 Manual Test Ping from Alpha Warrior"
    return send_telegram(message)

@app.route('/run')
def scheduled_ping():
    now_ist = datetime.utcnow() + timedelta(hours=5, minutes=30)
    current_time = now_ist.strftime('%H:%M')

    if current_time in ["09:15", "09:16", "09:17"]:
        top_stocks = get_top_stock_picks()
        message = "📈 Quant Investing Alert\n"
        for i, stock in enumerate(top_stocks, 1):
            message += f"✅ Pick {i}: {stock['name']} – Score: {stock['score']}\n"
        return send_telegram(message)
    else:
        return f"⏳ Not 9:15 yet. Current IST time: {current_time}"

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": T_BOT_CHAT_ID,
        "text": message
    }
    r = requests.post(url, data=payload)
    return f"Sent: {r.status_code}"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
