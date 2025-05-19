
import os
import threading
from flask import Flask
from SmartApi.smartConnect import SmartConnect
from SmartApi.smartWebSocketV2 import SmartWebSocketV2
from nse_token_data_cleaned import nse_tokens
from screener_scraper import fetch_technical_data

# Flask app to keep Render alive
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running."

def hybrid_filters(stock):
    try:
        price = float(stock.get("price", 0))
        high_52 = float(stock.get("52w high", 0))
        sma_150 = float(stock.get("SMA150", 0))
        sma_50_vol = float(stock.get("50DMA Volume", 0))
        curr_vol = float(stock.get("Volume", 0))

        if (
            price > sma_150 and
            price >= 0.9 * high_52 and
            curr_vol > sma_50_vol
        ):
            return True
    except:
        return False
    return False

def send_telegram_alert(symbol):
    import requests
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("T_BOT_CHAT_ID")
    message = f"ALERT: {symbol} matches criteria"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        requests.post(url, data={"chat_id": chat_id, "text": message})
    except Exception as e:
        print(f"Telegram error: {e}")

def run_bot():
    try:
        print("Logging in to SmartAPI...")
        obj = SmartConnect(api_key=os.getenv("SMARTAPI_API_KEY"))
        data = obj.generateSession(os.getenv("SMARTAPI_CLIENT_CODE"), os.getenv("SMARTAPI_PASSWORD"), os.getenv("SMARTAPI_TOTP"))
        jwt_token = data["data"]["jwtToken"]
        feed_token = obj.getfeedToken()
        print("Login successful.")

        print("Fetching data with yfinance...")
        symbols = [entry["symbol"] for entry in nse_tokens]
        fundamentals = fetch_technical_data(symbols)
        print("Filtering stocks...")
        selected = [f["symbol"] for f in fundamentals if hybrid_filters(f)]
        for symbol in selected:
            send_telegram_alert(symbol)
        print("Final picks:", selected)

        # Optional: start WebSocket if needed
        # sws = SmartWebSocketV2(obj.getfeedToken(), obj.client_code, jwt_token)
        # sws.connect()

    except Exception as e:
        print(f"Bot error: {e}")

if __name__ == "__main__":
    threading.Thread(target=run_bot).start()
    app.run(host="0.0.0.0", port=10000)
