from flask import Flask
from datetime import datetime
from time import sleep
import requests
import os
from angel_one_api import angel_login, get_top_stocks  # Your real logic functions
from telegram_bot import send_telegram_message         # Your real Telegram send function

app = Flask(__name__)

# === Secrets from Render Environment Variables ===
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
T_BOT_CHAT_ID = os.environ.get('T_BOT_CHAT_ID')

@app.route('/run')
def run_bot():
    current_time = datetime.now().strftime("%H:%M")
    if "09:13" <= current_time <= "09:22":
        try:
            token = angel_login()
            try:
                top_stocks = get_top_stocks(token)  # LIVE fetching logic here
            except Exception as e:
                print("⚠️ First fetch failed, retrying...")
                sleep(3)
                top_stocks = get_top_stocks(token)

            message = "✅ Alpha Warrior Live Picks\n"
            for idx, stock in enumerate(top_stocks[:2], 1):
                message += f"✅ Pick {idx}: {stock['symbol']} – Score: {stock['score']:.2f}\n"

            send_telegram_message(message)
            return "✅ Live picks sent to Telegram."

        except Exception as e:
            error_msg = f"⚠️ Alpha Warrior Error: {e}"
            send_telegram_message(error_msg)
            return error_msg
    else:
        return f"⌛ Waiting... Current time: {current_time}"

@app.route('/wakeup')
def wakeup():
    try:
        token = angel_login()
        print("✅ Warm-up successful.")
        return "✅ Alpha Warrior is awake and logged in."
    except Exception as e:
        print(f"❌ Wakeup failed: {e}")
        return f"❌ Wakeup failed: {e}"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=81)
