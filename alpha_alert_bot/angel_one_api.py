import os
import requests
from smartapi.smartConnect import SmartConnect
from datetime import datetime
import json

# Send message to Telegram
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

# Get top 2 stocks
def get_top_stocks(nse_tokens):
    top_symbols = [entry["symbol"] for entry in nse_tokens[:2]]
    return top_symbols

# Start websocket and send alerts
def start_websocket():
    print("Sending login request...")

    api_key = os.environ.get("SMARTAPI_API_KEY")
    client_code = os.environ.get("SMARTAPI_CLIENT_CODE")
    pin = os.environ.get("SMARTAPI_PIN")
    totp = os.environ.get("SMARTAPI_TOTP")

    obj = SmartConnect(api_key)
    data = obj.generateSession(client_code, pin, totp)
    jwt_token = data["data"]["jwtToken"]

    # Get token list from environment variable or replace with actual logic
    nse_tokens = json.loads(os.environ.get("NSE_TOKENS", "[]"))

    symbols = get_top_stocks(nse_tokens)

    token_map = {entry["symbol"]: entry["token"] for entry in nse_tokens}
    message = f"<b>Quant Picks {datetime.now().strftime('%d-%b-%Y')}</b>\n\n"

    for i, symbol in enumerate(symbols, start=1):
        token = token_map[symbol]
        ltp_data = obj.get_ltp(exchange="NSE", tradingsymbol=symbol, symboltoken=token)
        ltp = ltp_data["data"]["ltp"]
        target = round(ltp * 1.2, 2)
        stop_loss = round(ltp * 0.9, 2)

        message += f"<b>Rank {i}: {symbol}</b>\n"
        message += f"Entry: {ltp}\nTarget: {target}\nStop Loss: {stop_loss}\n\n"

    send_telegram(message)
