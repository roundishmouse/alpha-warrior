
import os
import requests
import json
from datetime import datetime, timedelta

def send_telegram(message):
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("T_BOT_CHAT_ID")
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        r = requests.post(url, data=payload)
        print("Telegram sent:", r.text)
    except Exception as e:
        print("Telegram Error:", e)

def start_websocket():
    # Sample picks
    picks = [
        {"symbol": "INFY", "entry": 1400, "target": 1680, "stop_loss": 1260, "rank": 1},
        {"symbol": "TATAMOTORS", "entry": 920, "target": 1104, "stop_loss": 828, "rank": 2}
    ]
    today = datetime.now().strftime("%d-%b-%Y")
    message = f"*📊 Top Quant Picks - {today}"

    for stock in picks:
        message += (
            f"*🏅 Rank #{stock['rank']}*: `{stock['symbol']}`\n"
            f"➤ Entry: ₹{stock['entry']}\n"
            f"🎯 Target: ₹{stock['target']}\n"
            f"🛡 Stop Loss: ₹{stock['stop_loss']}\n"
            f"📅 Exit by: {(datetime.now() + timedelta(days=30)).strftime('%d-%b-%Y')}\n\n"
        )
    send_telegram(message)
