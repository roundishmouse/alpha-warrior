import os
import requests
import pyotp
from smartapi_python.smartconnect import SmartConnect
from datetime import datetime

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

# Stock filter logic (simplified)
def get_top_stocks(nse_tokens, obj):
    qualified = []

    for entry in nse_tokens:
        symbol = entry["symbol"]
        token = entry["token"]

        try:
            ltp_data = obj.get_ltp(exchange="NSE", tradingsymbol=symbol, symboltoken=token)
            ltp = ltp_data["data"]["ltp"]
            score = ltp  # simplified score
            qualified.append((symbol, token, ltp, score))
        except Exception:
            continue

    qualified.sort(key=lambda x: -x[3])
    return qualified[:2]

# Main bot trigger
def start_websocket():
    print("Running Alpha Warrior with SmartAPI + TOTP...")

    api_key = os.environ.get("SMARTAPI_API_KEY")
    client_code = os.environ.get("SMARTAPI_CLIENT_CODE")
    pin = os.environ.get("SMARTAPI_PIN")
    totp_secret = os.environ.get("SMARTAPI_TOTP")

    # Generate TOTP dynamically
    totp = pyotp.TOTP(totp_secret).now()
    obj = SmartConnect(api_key)

    try:
        data = obj.generateSession(client_code, pin, totp)
        jwtToken = data.get("data", {}).get("jwtToken")
        print("Login successful. JWT:", jwtToken)
    except Exception as e:
        print("Login failed:", e)
        return

    from nse_token_data import nse_tokens
    stocks = get_top_stocks(nse_tokens, obj)

    message = f"<b>Top Picks {datetime.now().strftime('%d-%b-%Y')}:</b>\n"
    for i, stock in enumerate(stocks, 1):
        symbol, token, ltp, score = stock
        message += f"<b>#{i} {symbol}</b>\nLTP: {ltp}\nScore: {round(score, 2)}\n\n"

    send_telegram(message)
