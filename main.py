from flask import Flask
import os
import requests
import pandas as pd
import pyotp
from datetime import datetime, timedelta

app = Flask(__name__)

# === SECRETS ===
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
T_BOT_CHAT_ID = os.environ.get('T_BOT_CHAT_ID')
ANGEL_API_KEY = os.environ.get('ANGEL_API_KEY')
ANGEL_CLIENT_ID = os.environ.get('ANGEL_CLIENT_ID')
ANGEL_PIN = os.environ.get('ANGEL_PIN')
ANGEL_TOTP_SECRET = os.environ.get('ANGEL_TOTP_SECRET')

# === AngelOne Login Function ===
def angel_login():
    # Generate TOTP dynamically
    totp = pyotp.TOTP(ANGEL_TOTP_SECRET).now()
    payload = {
        "clientcode": ANGEL_CLIENT_ID,
        "password": ANGEL_PIN,
        "totp": totp
    }
    headers = {
        "Content-Type": "application/json",
        "X-API-KEY": ANGEL_API_KEY
    }
    response = requests.post('https://apiconnect.angelbroking.com/rest/auth/angelbroking/user/v1/loginByPassword', json=payload, headers=headers)
    data = response.json()
    if data.get('status') == True:
        return data['data']['jwtToken']
    else:
        raise Exception(f"Login failed: {data}")

# === Stock Fetcher & Ranker ===
def get_top_stocks(auth_token):
    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
        "X-API-KEY": ANGEL_API_KEY
    }
    
    # For demo purposes, we assume fetching 10 dummy stocks
    # Later you can expand to Nifty100+Midcap150+Smallcap150
    stocks = [
        {"symbol": "TATAMOTORS", "momentum": 87, "value": 78, "volume": 90},
        {"symbol": "CUMMINSIND", "momentum": 85, "value": 80, "volume": 88},
        {"symbol": "HDFCBANK", "momentum": 75, "value": 84, "volume": 83},
        {"symbol": "ICICIBANK", "momentum": 88, "value": 77, "volume": 85},
        {"symbol": "BAJFINANCE", "momentum": 82, "value": 79, "volume": 81},
    ]
    
    df = pd.DataFrame(stocks)
    df['score'] = 0.5 * df['momentum'] + 0.3 * df['value'] + 0.2 * df['volume']
    df = df.sort_values(by='score', ascending=False).head(2)
    top_stocks = df.to_dict(orient='records')
    
    return top_stocks

# === Telegram Sender ===
def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": T_BOT_CHAT_ID,
        "text": message
    }
    requests.post(url, data=payload)

# === Scheduled Ping ===
@app.route('/run')
def run_job():
    current_time = datetime.now().strftime("%H:%M")
    if "09:15" <= current_time <= "09:20":
        try:
            token = angel_login()
            top_stocks = get_top_stocks(token)
            message = "🚀 Alpha Warrior Live Picks\n"
            for idx, stock in enumerate(top_stocks, 1):
                message += f"✅ Pick {idx}: {stock['symbol']} – Score: {stock['score']:.2f}\n"
            send_telegram_message(message)
            return "✅ Ping sent!"
        except Exception as e:
            return f"❌ Error: {e}"
    else:
        return f"⏳ Waiting... Current time {current_time}"

# === Home Page ===
@app.route('/')
def home():
    return "✅ Alpha Warrior 2.0 is running perfectly!"

# === Manual Test Ping ===
@app.route('/test')
def test_ping():
    send_telegram_message("🛠️ Manual test ping from Alpha Warrior 2.0")
    return "✅ Test ping sent!"

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=81)
