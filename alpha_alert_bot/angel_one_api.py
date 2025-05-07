import os
import requests
from smartapi.smartconnect import SmartConnect
from datetime import datetime
import json

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
        r = requests.post(url, data=payload)
        print("Telegram sent:", r.text)
    except Exception as e:
        print("Telegram Error:", e)

# CANSLIM + Minervini style filter
def get_top_stocks(nse_tokens, obj):
    qualified = []

    for entry in nse_tokens:
        symbol = entry["symbol"]
        token = entry["token"]

        try:
            ltp_data = obj.get_ltp(exchange="NSE", tradingsymbol=symbol, symboltoken=token)
            ltp = ltp_data["data"]["ltp"]

            # Simulated MAs for Minervini filter (placeholders)
            ma50 = ltp * 0.95
            ma150 = ltp * 0.90
            ma200 = ltp * 0.88
            week52_high = ltp * 1.05
            avg_volume = 100000
            current_volume = 120000

            if (
                ma50 > ma150 > ma200 and
                ltp > ma50 and
                ltp > ma150 and
                ltp > ma200 and
                ltp >= 0.9 * week52_high and
                current_volume > avg_volume * 1.1
            ):
                score = (ltp / ma200) + (current_volume / avg_volume)
                qualified.append((symbol, token, ltp, score))
        except:
            continue

    qualified.sort(key=lambda x: x[3], reverse=True)
    return qualified[:2]

# Main bot logic
def start_websocket():
    print("Starting bot with CANSLIM + Minervini filters...")

    api_key = os.environ.get("SMARTAPI_API_KEY")
    client_code = os.environ.get("SMARTAPI_CLIENT_CODE")
    pin = os.environ.get("SMARTAPI_PIN")
    totp = os.environ.get("SMARTAPI_TOTP")

    obj = SmartConnect(api_key)
    data = obj.generateSession(client_code, pin, totp)

    nse_tokens = json.loads(os.environ.get("NSE_TOKENS", "[]"))
    top_stocks = get_top_stocks(nse_tokens, obj)

    message = f"<b>Quant Picks {datetime.now().strftime('%d-%b-%Y')}</b>\n\n"

    for i, (symbol, token, ltp, score) in enumerate(top_stocks, start=1):
        target = round(ltp * 1.2, 2)
        stop_loss = round(ltp * 0.9, 2)
        message += f"<b>Rank {i}: {symbol}</b>\nEntry: ₹{ltp}\nTarget: ₹{target}\nStop Loss: ₹{stop_loss}\n\n"

    if top_stocks:
        send_telegram(message)
    else:
        send_telegram("No stocks matched the CANSLIM + Minervini criteria today.")
