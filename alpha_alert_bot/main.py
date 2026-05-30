import os
import time
import math
import json
import threading
from datetime import datetime, timedelta
from flask import Flask
from SmartApi.smartConnect import SmartConnect
import pyotp
import requests
import yfinance as yf
from nse_token_data_cleaned import nse_tokens
from dotenv import load_dotenv
from trade_manager import auto_buy, get_available_capital, get_open_position_count

load_dotenv()

app = Flask(__name__)

# ============================================================
# CONFIGURATION
# ============================================================
MIN_SCORE = 7
MAX_PRICE = 5000
MIN_VOLUME = 50000
COOLDOWN_DAYS = 7
TOP_N = 2
ALERT_LOG_FILE = "alert_log.json"
CAPITAL_PER_TRADE = 50000
MAX_POSITIONS = 3

ETF_KEYWORDS = [
    "ETF", "BEES", "GSEC", "TBILL", "LIQUID", "GILT",
    "BOND", "NIFTY", "SENSEX", "JUNIOR", "NEXT50",
    "HDFCNIF", "EQUAL50", "MOM50", "MOM100", "LOWVOL",
    "DIVGIT", "BANKBEES", "CPSEETF", "PSUBNKBEES"
]

@app.route("/")
def home():
    return "Alpha Warrior is running."

def send_telegram_alert(stock):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("T_BOT_CHAT_ID")
    message = (
        f"🚀 ALERT: {stock['symbol']}\n"
        f"💰 Price: ₹{stock['price']}\n"
        f"⭐ Score: {stock['score']:.2f}/7\n"
        f"📈 52W High: ₹{stock['52w high']}\n"
        f"📊 Vol Ratio: {round(stock['Volume'] / stock['SOMA Volume'], 2) if stock['SOMA Volume'] else 'N/A'}x\n"
        f"🕐 {datetime.now().strftime('%d-%b-%Y %H:%M')}"
    )
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        requests.post(url, data={"chat_id": chat_id, "text": message})
    except Exception as e:
        print(f"Telegram error: {e}")

def send_telegram_message(text):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("T_BOT_CHAT_ID")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        requests.post(url, data={"chat_id": chat_id, "text": text})
    except Exception as e:
        print(f"Telegram error: {e}")

def load_alert_log():
    try:
        with open(ALERT_LOG_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_alert_log(log):
    try:
        with open(ALERT_LOG_FILE, "w") as f:
            json.dump(log, f, indent=2)
    except Exception as e:
        print(f"Error saving alert log: {e}")

def was_recently_alerted(symbol):
    log = load_alert_log()
    if symbol in log:
        last_date = datetime.strptime(log[symbol], "%Y-%m-%d")
        if datetime.now() - last_date < timedelta(days=COOLDOWN_DAYS):
            print(f"  ⏩ {symbol} alerted {(datetime.now() - last_date).days}d ago — skipping")
            return True
    return False

def mark_as_alerted(symbol):
    log = load_alert_log()
    log[symbol] = datetime.now().strftime("%Y-%m-%d")
    save_alert_log(log)

def is_etf_or_bond(symbol):
    sym_upper = symbol.upper()
    return any(keyword in sym_upper for keyword in ETF_KEYWORDS)

def safe_float(val):
    try:
        val = float(val)
        return 0 if math.isnan(val) else val
    except:
        return 0

def hybrid_filters(stock):
    try:
        symbol = stock.get("symbol", "")
        if is_etf_or_bond(symbol):
            return False
        price = safe_float(stock.get("price"))
        if price <= 0 or price > MAX_PRICE:
            return False
        high_52 = safe_float(stock.get("52w high"))
        sma150 = safe_float(stock.get("SMA150"))
        sma_vol = safe_float(stock.get("SOMA Volume"))
        curr_vol = safe_float(stock.get("Volume"))
        if curr_vol < MIN_VOLUME:
            return False
        return (
            price > 0.75 * high_52 and
            price > sma150 and
            curr_vol > sma_vol
        )
    except:
        return False

def score_stock(stock):
    score = 0
    price = stock["price"]
    high_52 = stock["52w high"]
    sma20 = stock["SMA20"]
    sma50 = stock["SMA50"]
    sma150 = stock["SMA150"]
    vol = stock["Volume"]
    vol50 = stock["SOMA Volume"]
    proximity = price / high_52 if high_52 else 0
    if proximity >= 0.95:
        score += 2
    elif proximity >= 0.90:
        score += 1
    if price > sma20:
        score += 1
    if price > sma50:
        score += 1
    if price > sma150:
        score += 1
    vol_ratio = vol / vol50 if vol50 else 0
    if vol_ratio > 2:
        score += 2
    elif vol_ratio > 1.5:
        score += 1
    stock["score"] = score
    return stock

def fetch_technical_data(symbols):
    data = []
    for idx, symbol in enumerate(symbols):
        try:
            print(f"Fetching {idx+1}/{len(symbols)}: {symbol}")
            yf_symbol = symbol if symbol.endswith(".NS") else symbol + ".NS"
            stock = yf.Ticker(yf_symbol)
            hist = stock.history(period="300d")
            if hist.empty:
                continue
            current_price = hist["Close"].iloc[-1]
            high_52 = hist["High"].rolling(window=252).max().iloc[-1]
            sma20 = hist["Close"].rolling(window=20).mean().iloc[-1]
            sma50 = hist["Close"].rolling(window=50).mean().iloc[-1]
            sma150 = hist["Close"].rolling(window=150).mean().iloc[-1]
            sma_vol = hist["Volume"].rolling(window=50).mean().iloc[-1]
            curr_vol = hist["Volume"].iloc[-1]
            data.append({
                "symbol": symbol,
                "price": round(current_price, 2),
                "52w high": round(high_52, 2),
                "SMA20": round(sma20, 2),
                "SMA50": round(sma50, 2),
                "SMA150": round(sma150, 2),
                "SOMA Volume": round(sma_vol, 2),
                "Volume": round(curr_vol, 2),
            })
        except Exception as e:
            print(f"Error fetching {symbol}: {e}")
    return data

def is_market_bullish():
    try:
        nifty = yf.Ticker("^NSEI")
        hist = nifty.history(period="300d")
        if hist.empty:
            print("Failed to fetch Nifty data.")
            return False
        current = hist["Close"].iloc[-1]
        sma50 = hist["Close"].rolling(window=50).mean().iloc[-1]
        ema200 = hist["Close"].ewm(span=200, adjust=False).mean().iloc[-1]
        print(f"Nifty: {round(current, 2)}, SMA50: {round(sma50, 2)}, EMA200: {round(ema200, 2)}")
        is_bullish = current > sma50 and current > ema200
        print(f"Market is {'BULLISH ✅' if is_bullish else 'NOT bullish ❌'}")
        return is_bullish
    except Exception as e:
        print(f"Error checking market trend: {e}")
        return False

def run_bot():
    try:
        print("=" * 50)
        print(f"Alpha Warrior — {datetime.now().strftime('%d-%b-%Y %H:%M')}")
        print("=" * 50)
        print("Logging in to SmartAPI...")
        api_key = os.getenv("SMARTAPI_API_KEY")
        client_code = os.getenv("SMARTAPI_CLIENT_CODE")
        password = os.getenv("SMARTAPI_PASSWORD")
        totp_secret = os.getenv("SMARTAPI_TOTP")
        totp = pyotp.TOTP(totp_secret).now()
        time.sleep(5)
        obj = SmartConnect(api_key=api_key)
        obj.generateSession(client_code, password, totp)
        print("Login successful.")

        if not is_market_bullish():
            print("Market is not bullish. Skipping scan.")
            send_telegram_message(
                f"⚠️ Alpha Warrior: Market not bullish ({datetime.now().strftime('%d-%b-%Y')}). No scan."
            )
            return

        available = get_available_capital()
        open_count = get_open_position_count()
        print(f"Available capital: ₹{available:,.0f}")
        print(f"Open positions: {open_count}/{MAX_POSITIONS}")

        if available < CAPITAL_PER_TRADE:
            msg = f"⚠️ Alpha Warrior: Insufficient capital (₹{available:,.0f}). Need ₹{CAPITAL_PER_TRADE:,.0f}."
            print(msg)
            send_telegram_message(msg)
            return

        if open_count >= MAX_POSITIONS:
            msg = f"⚠️ Alpha Warrior: Max {MAX_POSITIONS} positions open. Waiting for exit."
            print(msg)
            send_telegram_message(msg)
            return

        symbols = [entry["symbol"] for entry in nse_tokens]
        print(f"Scanning {len(symbols)} symbols...")
        tech_data = fetch_technical_data(symbols)
        print(f"Technical data fetched: {len(tech_data)}")
        filtered = [s for s in tech_data if hybrid_filters(s)]
        print(f"Stocks after hybrid filter: {len(filtered)}")

        if not filtered:
            print("No stocks matched today.")
            send_telegram_message(
                f"ℹ️ Alpha Warrior: No stocks matched filters ({datetime.now().strftime('%d-%b-%Y')})."
            )
            return

        scored = [score_stock(s) for s in filtered]
        high_quality = [s for s in scored if s["score"] >= MIN_SCORE]
        print(f"Stocks with score >= {MIN_SCORE}: {len(high_quality)}")

        if not high_quality:
            print(f"No stocks scored >= {MIN_SCORE} today.")
            send_telegram_message(f"ℹ️ Alpha Warrior: No stocks scored >= {MIN_SCORE} today.")
            return

        ranked = sorted(high_quality, key=lambda x: x["score"], reverse=True)
        fresh_picks = [s for s in ranked if not was_recently_alerted(s["symbol"])]

        if not fresh_picks:
            print("All picks recently alerted.")
            send_telegram_message("ℹ️ Alpha Warrior: All picks recently alerted. No new trades today.")
            return

        slots_available = MAX_POSITIONS - open_count
        top_stocks = fresh_picks[:min(TOP_N, slots_available)]

        for stock in top_stocks:
            symbol = stock["symbol"]
            price = stock["price"]
            send_telegram_alert(stock)
            mark_as_alerted(symbol)
            print(f"✅ Alert sent for {symbol} (Score: {stock['score']})")
            print(f"🔵 Initiating auto buy for {symbol}...")
            time.sleep(3)
            success = auto_buy(symbol, price)
            if success:
                print(f"✅ Auto buy successful for {symbol}")
            else:
                print(f"❌ Auto buy failed for {symbol}")

        print(f"\nDone! Processed {len(top_stocks)} stock(s) today.")

    except Exception as e:
        error_msg = f"❌ Alpha Warrior error: {e}"
        print(error_msg)
        send_telegram_message(error_msg)

if __name__ == "__main__":
    threading.Thread(target=run_bot).start()
    app.run(host="0.0.0.0", port=10000)
