from flask import Flask
import os
import requests
import pyotp
import json
from SmartApi import SmartConnect
from datetime import datetime, timedelta

app = Flask(__name__)

# ==== YOUR ANGEL ONE CREDENTIALS ====
client_id = "A505883"
client_password = "1208Amit@9179"
api_key = "Y4QqCf01"
totp_secret = "3NO6IXIOTSDBEROL7QNWETWDEY"

# ==== TELEGRAM CREDENTIALS ====
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
T_BOT_CHAT_ID = os.environ.get('T_BOT_CHAT_ID')

# ==== Helper Functions ====

def generate_totp():
    totp = pyotp.TOTP(totp_secret)
    return totp.now()

def login_smartapi():
    obj = SmartConnect(api_key=api_key)
    data = obj.generateSession(client_id, client_password, generate_totp())
    return obj

def fetch_live_stocks():
    # Fetch NIFTY100, MIDCAP150, SMALLCAP150
    indices = [
        "NIFTY 100",
        "NIFTY MIDCAP 150",
        "NIFTY SMLCAP 150"
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    all_stocks = []

    for index in indices:
        url = f"https://www.nseindia.com/api/equity-stockIndices?index={index}"
        try:
            r = requests.get(url, headers=headers, timeout=5)
            if r.status_code == 200:
                data = r.json()
                for stock in data['data']:
                    symbol = stock['symbol']
                    last_price = float(str(stock['lastPrice']).replace(',', ''))
                    high_52w = float(str(stock['yearHigh']).replace(',', ''))
                    low_52w = float(str(stock['yearLow']).replace(',', ''))
                    volume = stock.get('totalTradedVolume', 0)
                    
                    all_stocks.append({
                        "symbol": symbol,
                        "last_price": last_price,
                        "high_52w": high_52w,
                        "low_52w": low_52w,
                        "volume": volume
                    })
        except Exception as e:
            print(f"Error fetching {index}: {e}")
            continue
    
    return all_stocks

def score_stocks(stock_list):
    eligible = []

    for stock in stock_list:
        try:
            price_ok = stock['last_price'] >= 0.75 * stock['high_52w']
            if price_ok and stock['volume'] > 0:
                # Simulate Volume Spike (we assume average volume is around 2/3rd of today's volume for now)
                volume_spike_ok = stock['volume'] >= 1.5 * (stock['volume'] / 1.5)

                if volume_spike_ok:
                    # Momentum Score (price near 52W high)
                    momentum_score = 80 + (stock['last_price'] / stock['high_52w']) * 20  # between 80-100
                    # Value Score (lower price closer to 52W low is better value)
                    value_score = 100 - (stock['last_price'] - stock['low_52w']) / (stock['high_52w'] - stock['low_52w']) * 100
                    final_score = (0.6 * momentum_score) + (0.4 * value_score)

                    stock['momentum_score'] = momentum_score
                    stock['value_score'] = value_score
                    stock['final_score'] = final_score

                    eligible.append(stock)
        except:
            continue

    eligible.sort(key=lambda x: x['final_score'], reverse=True)
    return eligible[:2]

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": T_BOT_CHAT_ID,
        "text": message
    }
    requests.post(url, data=payload)

@app.route('/')
def home():
    return "✅ Alpha Warrior 2.0 LIVE - Full Machine Version Running!"

@app.route('/run')
def scheduled_ping():
    now_ist = datetime.utcnow() + timedelta(hours=5, minutes=30)
    current_time = now_ist.strftime("%H:%M")

    if current_time in ["09:13", "09:14", "09:15", "09:16"]:
        try:
            obj = login_smartapi()  # Only needed for formal login
            live_stocks = fetch_live_stocks()
            top_picks = score_stocks(live_stocks)

            if top_picks:
                message = "🚀 LIVE Stock Picks from Alpha Warrior:\n"
                for i, stock in enumerate(top_picks, 1):
                    message += f"✅ Pick {i}: {stock['symbol']} - ₹{stock['last_price']} (Score: {stock['final_score']:.2f})\n"
                send_telegram(message)
                return f"✅ Success: Picks sent at {current_time}"
            else:
                send_telegram("⚡ No strong stocks found today.")
                return "⚡ No eligible stocks today."
        except Exception as e:
            send_telegram(f"❌ Error: {str(e)}")
            return f"❌ Error occurred: {str(e)}"
    else:
        return f"⏱️ Current IST time is {current_time} — waiting for 9:13–9:16."

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=81)
