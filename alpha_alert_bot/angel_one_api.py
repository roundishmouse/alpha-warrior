import os
import json
import requests
import re
from datetime import datetime, timedelta
from nse_token_data import nse_tokens

# Escape special characters for MarkdownV2
def escape_md(text):
    return re.sub(r'([_*[\]()~`>#+=|{}.!-])', r'\\\1', str(text))

def send_telegram(message):
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("T_CHAT_ID")
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "MarkdownV2"
    }
    
    try:
        r = requests.post(url, data=payload)
        print("Telegram sent:", r.text)
    except Exception as e:
        print("Telegram Error:", e)

def get_token_for_symbols(symbols):
    token_map = {entry["symbol"]: entry["token"] for entry in nse_tokens}
    result = []
    
    for i, symbol in enumerate(symbols[:10], start=1):  # limit to top 10
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
    final_top_picks = [entry["symbol"] for entry in nse_tokens][:10]  # Top 10 symbols
    picks = get_token_for_symbols(final_top_picks)
    
    today = datetime.now().strftime("%d-%b-%Y")
    message = f"*Quant Picks – {escape_md(today)}*\n\n"
    
    for stock in picks:
        message += f"*Rank:* {escape_md(stock['rank'])} | *Symbol:* {escape_md(stock['symbol'])}\n"
        message += f"*Entry:* {escape_md(stock['entry'])}\n"
        message += f"*Target:* {escape_md(stock['target'])}\n"
        message += f"*Stop Loss:* {escape_md(stock['stop_loss'])}\n\n"
    
    send_telegram(message)
