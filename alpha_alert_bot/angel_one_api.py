import os
import requests
import yfinance as yf
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

# Calculate real technicals using yfinance data
def get_real_indicators(symbol):
    try:
        yf_symbol = symbol + ".NS"
        data = yf.download(yf_symbol, period="250d", interval="1d", progress=False)
        if data.empty or len(data) < 200:
            return None

        closes = data["Close"]
        volume = data["Volume"]
        ltp = closes.iloc[-1]
        ma50 = closes[-50:].mean()
        ma150 = closes[-150:].mean()
        ma200 = closes[-200:].mean()
        week52_high = closes.max()
        avg_volume = volume[-20:].mean()

        return {
            "ltp": ltp,
            "ma50": ma50,
            "ma150": ma150,
            "ma200": ma200,
            "week52_high": week52_high,
            "avg_volume": avg_volume
        }
    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")
        return None

# Final stock ranking logic
def get_top_stocks(nse_tokens, obj):
    qualified = []

    for entry in nse_tokens:
        symbol = entry["symbol"]
        token = entry["token"]

        indicators = get_real_indicators(symbol)
        if not indicators:
            continue

        try:
            ltp_data = obj.get_ltp(exchange="NSE", tradingsymbol=symbol, symboltoken=token)
            ltp = ltp_data["data"]["ltp"]
        except:
            continue

        if (
            indicators["ma50"] > indicators["ma150"] > indicators["ma200"] and
            indicators["ltp"] > indicators["ma50"] and
            indicators["ltp"] >= 0.9 * indicators["week52_high"]
        ):
            score = (indicators["ltp"] / indicators["ma200"])
            qualified.append((symbol, token, indicators["ltp"], score))

    qualified.sort(key=lambda x: x[3], reverse=True)
    return qualified[:2]

# Main bot trigger
def start_websocket():
    print("Running Alpha Warrior with real filters...")

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
        send_telegram("No stocks matched the CANSLIM + Minervini filters today.")
