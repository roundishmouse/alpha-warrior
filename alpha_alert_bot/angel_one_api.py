import os
import requests
import json
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
    from token_list import final_top_picks as picks

    # Get live tokens
    symbols = [stock['symbol'] for stock in picks]
    token_map = get_token_for_symbols(symbols)

    today = datetime.now().strftime("%d-%b-%Y")
    message = f"<b>⚡ Top Quant Picks – {today}</b>\n\n"

    for stock in picks:
        token = token_map.get(stock['symbol'], 'N/A')
        message += f"<b>#{stock['rank']} {stock['symbol']} ({token})</b>\n"
        message += f"Entry: {stock['entry']}\n"
        message += f"Target: {stock['target']}\n"
        message += f"Stop Loss: {stock['stop_loss']}\n"
        message += f"Exit by: {(datetime.now() + timedelta(days=30)).strftime('%d-%b-%Y')}\n\n"

    send_telegram(message)
