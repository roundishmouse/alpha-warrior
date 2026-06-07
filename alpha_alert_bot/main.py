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
MAX_PREV_DAY_MOVE = 5.0  # NEW: Skip if stock moved >5% yesterday

ETF_KEYWORDS = [
    "ETF", "BEES", "GSEC", "TBILL", "LIQUID", "GILT",
    "BOND", "NIFTY", "SENSEX", "JUNIOR", "NEXT50",
    "HDFCNIF", "EQUAL50", "MOM50", "MOM100", "LOWVOL",
    "DIVGIT", "BANKBEES", "CPSEETF", "PSUBNKBEES"
]

# ============================================================
# FLASK KEEP-ALIVE
# ============================================================
@app.route("/")
def home():
    return "Alpha Warrior is running."


# ============================================================
# TELEGRAM
# ============================================================
def send_telegram_alert(stock):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("T_BOT_CHAT_ID")
    message = (
        f"🚀 ALERT: {stock['symbol']}\n"
        f"💰 Price: ₹{stock['price']}\n"
        f"⭐ Score: {stock['score']:.2f}/7\n"
        f"📈 52W High: ₹{stock['52w high']}\n"
        f"📊 Vol Ratio: {round(stock['Volume'] / stock['SOMA Volume'], 2) if stock['SOMA Volume'] else 'N/A'}x\n"
        f"📉 Prev Day Move: {stock.get('prev_day_move', 0):.2f}%\n"
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


# ============================================================
# COOLDOWN TRACKER
# ============================================================
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


# ============================================================
# ETF FILTER
# ============================================================
def is_etf_or_bond(symbol):
    sym_upper = symbol.upper()
    return any(keyword in sym_upper for keyword in ETF_KEYWORDS)


# ============================================================
# SAFE FLOAT
# ============================================================
def safe_float(val):
    try:
        val = float(val)
        return 0 if math.isnan(val) else val
    except:
        return 0


# ============================================================
# HYBRID FILTERS — with NEW 5% previous day move filter
# ============================================================
def hybrid_filters(stock):
    try:
        symbol = stock.get("symbol", "")

        # Filter ETFs and bonds
        if is_etf_or_bond(symbol):
            return False

        price = safe_float(stock.get("price"))

        # Price cap
        if price <= 0 or price > MAX_PRICE:
            return False

        high_52 = safe_float(stock.get("52w high"))
        sma150 = safe_float(stock.get("SMA150"))
        sma_vol = safe_float(stock.get("SOMA Volume"))
        curr_vol = safe_float(stock.get("Volume"))

        # Minimum volume filter
        if curr_vol < MIN_VOLUME:
            return False

        # NEW: Previous day move filter — skip if moved >5% yesterday
        # Prevents chasing stocks that already made big moves
        prev_day_move = safe_float(stock.get("prev_day_move", 0))
        if prev_day_move > MAX_PREV_DAY_MOVE:
            print(f"  ⏩ {symbol} moved {prev_day_move:.1f}% yesterday — skipping (chasing filter)")
            return False

        # Original filters — unchanged
        return (
            price > 0.75 * high_52 and
            price > sma150 and
            curr_vol > sma_vol
        )
    except:
        return False


# ============================================================
# SCORE STOCK — unchanged
# ============================================================
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


# ============================================================
# FETCH TECHNICAL DATA — NEW: adds prev_day_move calculation
# ============================================================
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
            prev_price = hist["Close"].iloc[-2]
            high_52 = hist["High"].rolling(window=252).max().iloc[-1]
            sma20 = hist["Close"].rolling(window=20).mean().iloc[-1]
            sma50 = hist["Close"].rolling(window=50).mean().iloc[-1]
            sma150 = hist["Close"].rolling(window=150).mean().iloc[-1]
            sma_vol = hist["Volume"].rolling(window=50).mean().iloc[-1]
            curr_vol = hist["Volume"].iloc[-1]

            # NEW: Calculate previous day move %
            prev_day_move = ((current_price - prev_price) / prev_price) * 100

            data.append({
                "symbol": symbol,
                "price": round(current_price, 2),
                "prev_day_move": round(prev_day_move, 2),  # NEW
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


# ============================================================
# MARKET CONDITION — EMA200
# ============================================================
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


# ============================================================
# MAIN BOT
# ============================================================
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

        # Login confirmation
        send_telegram_message(
            f"✅ Alpha Warrior Online!\n"
            f"Angel One login successful\n"
            f"📅 {datetime.now().strftime('%d-%b-%Y %H:%M')}\n"
            f"🔍 Nifty scanning started..."
        )

        # Market check
        if not is_market_bullish():
            print("Market is not bullish. Skipping scan.")
            send_telegram_message(
                f"⚠️ Market not bullish ({datetime.now().strftime('%d-%b-%Y')})\n"
                f"Nifty below SMA50 or EMA200\n"
                f"No trades today. See you tomorrow! 🕐"
            )
            return

        # Capital check
        available = get_available_capital()
        open_count = get_open_position_count()
        print(f"Available capital: ₹{available:,.0f}")
        print(f"Open positions: {open_count}/{MAX_POSITIONS}")

        if available < CAPITAL_PER_TRADE:
            msg = (
                f"⚠️ Insufficient capital!\n"
                f"Available: ₹{available:,.0f}\n"
                f"Need: ₹{CAPITAL_PER_TRADE:,.0f}\n"
                f"Waiting for position to close..."
            )
            print(msg)
            send_telegram_message(msg)
            return

        if open_count >= MAX_POSITIONS:
            msg = (
                f"⚠️ Max positions reached!\n"
                f"Open: {open_count}/{MAX_POSITIONS}\n"
                f"Waiting for exit before new trade..."
            )
            print(msg)
            send_telegram_message(msg)
            return

        # Scan
        symbols = [entry["symbol"] for entry in nse_tokens]
        print(f"Scanning {len(symbols)} symbols...")
        tech_data = fetch_technical_data(symbols)
        print(f"Technical data fetched: {len(tech_data)}")

        filtered = [s for s in tech_data if hybrid_filters(s)]
        print(f"Stocks after hybrid filter: {len(filtered)}")

        if not filtered:
            print("No stocks matched today.")
            send_telegram_message(
                f"ℹ️ No stocks matched filters today\n"
                f"({datetime.now().strftime('%d-%b-%Y')})"
            )
            return

        scored = [score_stock(s) for s in filtered]
        high_quality = [s for s in scored if s["score"] >= MIN_SCORE]
        print(f"Stocks with score >= {MIN_SCORE}: {len(high_quality)}")

        if not high_quality:
            print(f"No stocks scored >= {MIN_SCORE} today.")
            send_telegram_message(
                f"ℹ️ No stocks scored >= {MIN_SCORE} today\n"
                f"Market bullish but no quality setups"
            )
            return

        ranked = sorted(high_quality, key=lambda x: x["score"], reverse=True)
        fresh_picks = [s for s in ranked if not was_recently_alerted(s["symbol"])]

        if not fresh_picks:
            print("All picks recently alerted.")
            send_telegram_message(
                f"ℹ️ All top picks alerted within last {COOLDOWN_DAYS} days\n"
                f"No new trades today"
            )
            return

        slots_available = MAX_POSITIONS - open_count
        top_stocks = fresh_picks[:min(TOP_N, slots_available)]

        for stock in top_stocks:
            symbol = stock["symbol"]
            price = stock["price"]
            send_telegram_alert(stock)
            mark_as_alerted(symbol)
            print(f"✅ Alert sent for {symbol} (Score: {stock['score']}, Prev move: {stock.get('prev_day_move', 0):.1f}%)")
            print(f"🔵 Initiating auto buy for {symbol}...")
            time.sleep(3)
            success = auto_buy(symbol, price)
            if success:
                print(f"✅ Auto buy successful for {symbol}")
            else:
                print(f"❌ Auto buy failed for {symbol}")
                send_telegram_message(f"❌ Auto buy FAILED for {symbol}. Please check manually!")

        print(f"\nDone! Processed {len(top_stocks)} stock(s) today.")

    except Exception as e:
        error_msg = f"❌ Alpha Warrior error: {e}"
        print(error_msg)
        send_telegram_message(error_msg)


# ============================================================
# ENTRY POINT
# ============================================================
if __name__ == "__main__":
    threading.Thread(target=run_bot).start()
    app.run(host="127.0.0.1", port=10000)
