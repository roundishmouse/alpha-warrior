import os
import requests
import pyotp
from smartapi.smartconnect import SmartConnect
from datetime import datetime
import json

def send_telegram(message):
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("T_BOT_CHAT_ID")
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print("Telegram Error:", e)

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
            if (ma50 > ma150 > ma200 and ltp > ma50 and ltp > ma150 and ltp > ma200 and
                    ltp >= 0.9 * week52_high and current_volume >= avg_volume * 1.1):
                score = (ltp / ma200) * (current_volume / avg_volume)
                qualified.append((symbol, token, ltp, score))
        except:
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

def start_websocket():
    print("Running Alpha Warrior with SmartAPI + TOTP...")

    api_key = os.environ.get("SMARTAPI_API_KEY")
    client_code = os.environ.get("SMARTAPI_CLIENT_CODE")
    pin = os.environ.get("SMARTAPI_PIN")
    totp_secret = os.environ.get("SMARTAPI_TOTP")

    # Generate TOTP dynamically
    totp = pyotp.TOTP(totp_secret).now()

    try:
        obj = SmartConnect()
        data = obj.generateSession(api_key=api_key, client_code=client_code, password=pin, totp=totp)
        jwtToken = obj.jwt_token
        print("Login successful. JWT:", jwtToken)
    except Exception as e:
        print("Login failed:", e)
        return

    from nse_token_data import nse_tokens
    symbols = get_top_stocks(nse_tokens, obj)

    is_fallback = len(symbols) == 0 or len(symbols[0]) == 0

    message = f"<b>{'Relaxed' if is_fallback else 'Quant'} Picks {datetime.now().strftime('%d-%b-%Y')}:</b>\n"
    message += f"Scanned: {len(nse_tokens)} | Selected: {len(symbols)}\n\n"

    for i, stock in enumerate(symbols, start=1):
        symbol, token, ltp = stock[:3]
        message += f"<b>#{i} {symbol}</b>\nLTP: {ltp}\n"
        if not is_fallback:
            message += f"Score: {round(stock[3], 2)}\n"
        message += "\n"

    send_telegram(message)
