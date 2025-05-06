import os
import requests
import json
from datetime import datetime, timedelta
from nse_token_data import nse_tokens

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

def get_token_for_symbols(symbols):
    token_map = {entry["symbol"]: entry["token"] for entry in nse_tokens}
    result = []
    for i, symbol in enumerate(symbols[:10], start=1):  # limit to top 10 for now
        if symbol in token_map:
            result.append({
                "rank": i,
                "symbol": symbol,
                "entry": "Live Price TBD",
                "target": "Target TBD",
                "stop_loss": "SL TBD"
            })
    return result

def start_websocket():
    final_top_picks = [entry["symbol"] for entry in nse_tokens]

    picks = get_token_for_symbols(final_top_picks)

    today = datetime.now().strftime("%d-%b-%Y")
    message = f"<b>Top Quant Picks – {today}</b>\n\n"

    for stock in picks:
        message += f"<b>Rank #{stock['rank']}</b>: {stock['symbol']}<br>"
        message += f"Entry: {stock['entry']}<br>"
        message += f"Target: {stock['target']}<br>"
        message += f"Stop Loss: {stock['stop_loss']}<br><br>"

    message += f"<i>Exit by {(datetime.now() + timedelta(days=10)).strftime('%d-%b-%Y')}</i><br><br>"

    send_telegram(message)
