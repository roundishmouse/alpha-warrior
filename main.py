from flask import Flask
import os
import requests

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
T_BOT_CHAT_ID = os.environ.get('T_BOT_CHAT_ID')

@app.route('/')
def home():
    return "✅ Alpha Warrior Bot is Live!"

@app.route('/test')
def send_test_message():
    message = "🔥 Test Ping from Alpha Warrior Bot on Render!"
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": T_BOT_CHAT_ID,
        "text": message
    }
    r = requests.post(url, data=payload)
    return f"Message Sent: {r.status_code}"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
