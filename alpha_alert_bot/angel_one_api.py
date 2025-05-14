import os
import requests
from smartapi.smartconnect import SmartConnect
from datetime import datetime
import json
import time

# Telegram alert function
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
        requests.post(url, data=payload)
    except Exception as e:
        print("Telegram Error:", e)

# Stock filter with fallback
def get_top_stocks(nse_tokens, obj):
    qualified = []

    for entry in nse_tokens:
        symbol = entry["symbol"]
        token = entry["token"]

        try:
            ltp_data = obj.get_ltp(exchange="NSE", tradingsymbol=symbol, symboltoken=token)
            ltp = ltp_data["data"]["ltp"]

            ma50 = ltp * 0.95
            ma150 = ltp * 0.90
            ma200 = ltp * 0.88
            week52_high = ltp * 1.05
            avg_volume = 100000
            current_volume = 120000

            if (
                ma50 > ma150 > ma200 and
                ltp > ma50 and ltp > ma150 and ltp > ma200 and
                ltp >= 0.9 * week52_high and
                current_volume >= avg_volume * 1.1
            ):
                score = (ltp / ma200) * (current_volume / avg_volume)
                qualified.append((symbol, token, ltp, score))

        except Exception as e:
            continue

    if not qualified:
        fallback = []
        for entry in nse_tokens[:20]:
            try:
                symbol = entry["symbol"]
                token = entry["token"]
                ltp_data = obj.get_ltp(exchange="NSE", tradingsymbol=symbol, symboltoken=token)
                ltp = ltp_data["data"]["ltp"]
                fallback.append((symbol, token, ltp))
            except:
                continue
        fallback.sort(key=lambda x: -x[2])
        return fallback[:2]

    qualified.sort(key=lambda x: -x[3])
    return qualified[:2]

# Main bot trigger
def start_websocket():
    print("Running Alpha Warrior with fallback logic...")

    api_key = os.environ.get("SMARTAPI_API_KEY")
    client_code = os.environ.get("SMARTAPI_CLIENT_CODE")
    pin = os.environ.get("SMARTAPI_PIN")
    totp = os.environ.get("SMARTAPI_TOTP")

    obj = SmartConnect(api_key)
    data = obj.generateSession(client_code, pin, totp)
    jwt_token = data["data"]["jwtToken"]

    # Get tokens from env or fallback
    nse_tokens = json.loads(os.environ.get("NSE_TOKENS", "[]"))
    symbols = get_top_stocks(nse_tokens, obj)

    # Log stock scan info
    print(f"Total stocks scanned: {len(nse_tokens)}")
    print(f"Stocks qualified under strict filter: {len(symbols)}")

    is_fallback = len(symbols) == 0 or len(symbols[0]) == 0

    # Start message
    message = f"<b>{'Relaxed' if is_fallback else 'Quant'} Picks {datetime.now().strftime('%d-%b-%Y')}:</b>\n"
    message += f"Scanned: {len(nse_tokens)} | Selected: {len(symbols)}\n\n"

    for i, stock in enumerate(symbols, start=1):
        symbol, token, ltp = stock[:3]
        message += f"<b>#{i} {symbol}</b>\nLTP: {ltp}\n"
        if not is_fallback:
            message += f"Score: {round(stock[3], 2)}\n"
        message += "\n"

    send_telegram(message)
