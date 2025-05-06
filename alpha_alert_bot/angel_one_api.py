import os
import requests
import json
import pandas as pd
from datetime import datetime, timedelta
from instrument_parser import get_token_for_symbols

def send_telegram(message):
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("T_BOT_CHAT_ID")
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        r = requests.post(url, data=payload)
        print("Telegram sent:", r.text)
    except Exception as e:
        print("Telegram Error:", e)

def start_websocket():
    # Load all NSE symbols from file
    df = pd.read_csv("nse_tokens.csv")
    final_top_picks = df["symbol"].tolist()

    # Convert to tokens
    picks = get_token_for_symbols(final_top_picks)

    # Format message
    today = datetime.now().strftime("%d-%b-%Y")
    message = f"<b>Top Quant Picks – {today}</b>\n\n"

    for stock in picks:
        message += f"<b>Rank #{stock['rank']}</b>: {stock['symbol']}<br>"
        message += f"Entry: {stock['entry']}<br>"
        message += f"Target: {stock['target']}<br>"
        message += f"Stop Loss: {stock['stop_loss']}<br><br>"

    message += f"<i>Exit by {(datetime.now() + timedelta(days=10)).strftime('%d-%b-%Y')}</i><br><br>"

    send_telegram(message)
