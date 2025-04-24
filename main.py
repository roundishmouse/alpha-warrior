from flask import Flask
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Quant Investor Bot is running!"
from datetime import datetime, timedelta
import os
import requests

# Convert UTC to IST
now_utc = datetime.utcnow()
now_ist = now_utc + timedelta(hours=5, minutes=30)
current_time = now_ist.strftime('%H:%M')

if current_time == "09:15":
    TELEGRAM_BOT_TOKEN = os.environ['TELEGRAM_BOT_TOKEN']
    T_BOT_CHAT_ID = os.environ['T_BOT_CHAT_ID']

    message = (
        "📈 Scheduled Quant Alert (Test for 20:45 IST)\n"
        "✅ Top Pick 1: CUMMINSIND – Score: 92.4\n"
        "✅ Top Pick 2: TATAMTRDVR – Score: 91.8"
    )

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": T_BOT_CHAT_ID,
        "text": message
    }
    headers = {"Content-Type": "application/json"}

    response = requests.post(url, json=payload, headers=headers)

    if response.status_code == 200:
        print("🎯 Test ping sent at 20:45 IST")
    else:
        print("❌ Failed to send ping:", response.text)
else:
    print(f"⏱️ Current IST time is {current_time} — waiting for 09:15 to send.")
    # Start the web server so Replit exposes your URL
    app.run(host='0.0.0.0', port=81)
