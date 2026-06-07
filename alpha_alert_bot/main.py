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
# BULL MODE settings (Nifty > EMA200)
BULL_CAPITAL_PER_TRADE = 50000
BULL_MAX_POSITIONS = 3
BULL_MIN_SCORE = 7
BULL_MAX_PREV_DAY_MOVE = 5.0
BULL_PRICE_PROXIMITY = 0.75  # Price > 75% of 52W high

# HUNT MODE settings (Nifty > SMA200)
HUNT_CAPITAL_PER_TRADE = 25000
HUNT_MAX_POSITIONS = 2
HUNT_MIN_SCORE = 7
HUNT_MAX_PREV_DAY_MOVE = 3.0  # Stricter — no chasing
HUNT_PRICE_PROXIMITY = 0.85  # Price > 85% of 52W high — near ATH only

# Common settings
MAX_PRICE = 5000
MIN_VOLUME = 50000
COOLDOWN_DAYS = 7
TOP_N = 2
ALERT_LOG_FILE = "alert_log.json"

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
def send_telegram_alert(stock, mode):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("T_BOT_CHAT_ID")
    mode_emoji = "🚀" if mode == "BULL" else "🎯"
    capital = BULL_CAPITAL_PER_TRADE if mode == "BULL" else HUNT_CAPITAL_PER_TRADE
    message = (
        f"{mode_emoji} [{mode} MODE] ALERT: {stock['symbol']}\n"
        f"💰 Price: ₹{stock['price']}\n"
        f"⭐ Score: {stock['score']:.2f}/7\n"
        f"📈 52W High: ₹{stock['52w high']}\n"
        f"📊 Vol Ratio: {round(stock['Volume'] / stock['SOMA Volume'], 2) if stock['SOMA Volume'] else 'N/A'}x\n"
        f"📉 Prev Day Move: {stock.get('prev_day_move', 0):.2f}%\n"
        f"💵 Deploying: ₹{capital:,.0f}\n"
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
    return any(keyword in symbol.upper() for keyword in ETF_KEYWORDS)


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
# HYBRID FILTERS — MODE AWARE
# ============================================================
def hybrid_filters(stock, mode):
    try:
        symbol = stock.get("symbol", "")

        # ETF filter
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
        prev_day_move = safe_float(stock.get("prev_day_move", 0))

        # Volume filter
        if curr_vol < MIN_VOLUME:
            return False

        # Mode specific settings
        if mode == "BULL":
            max_prev_move = BULL_MAX_PREV_DAY_MOVE
            price_proximity = BULL_PRICE_PROXIMITY
        else:  # HUNT
            max_prev_move = HUNT_MAX_PREV_DAY_MOVE
            price_proximity = HUNT_PRICE_PROXIMITY

        # Previous day move filter
        if prev_day_move > max_prev_move:
            print(f"  ⏩ {symbol} moved {prev_day_move:.1f}% yesterday — skipping")
            return False

        # Core filters with mode-specific proximity
        return (
            price > price_proximity * high_52 and
            price > sma150 and
            curr_vol > sma_vol
        )
    except:
        return False


# ============================================================
# SCORE STOCK
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
# FETCH TECHNICAL DATA
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
            prev_day_move = ((current_price - prev_price) / prev_price) * 100

            data.append({
                "symbol": symbol,
                "price": round(current_price, 2),
                "prev_day_move": round(prev_day_move, 2),
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
# MARKET CONDITION — DUAL MODE
# ============================================================
def get_market_mode():
    try:
        nifty = yf.Ticker("^NSEI")
        hist = nifty.history(period="300d")
        if hist.empty:
            print("Failed to fetch Nifty data.")
            return None

        current = hist["Close"].iloc[-1]
        sma50 = hist["Close"].rolling(window=50).mean().iloc[-1]
        sma200 = hist["Close"].rolling(window=200).mean().iloc[-1]
        ema200 = hist["Close"].ewm(span=200, adjust=False).mean().iloc[-1]

        print(f"Nifty: {round(current, 2)}")
        print(f"SMA50: {round(sma50, 2)}")
        print(f"SMA200: {round(sma200, 2)}")
        print(f"EMA200: {round(ema200, 2)}")

        # BULL MODE — strongest signal
        if current > sma50 and current > ema200:
            print("Mode: BULL 🚀")
            return "BULL"

        # HUNT MODE — moderate signal
        elif current > sma200:
            print("Mode: HUNT 🎯")
            return "HUNT"

        # Sleep — market too weak
        else:
            print("Mode: SLEEP 😴")
            return None

    except Exception as e:
        print(f"Error checking market: {e}")
        return None


# ============================================================
# MAIN BOT
# ============================================================
def run_bot():
    try:
        print("=" * 50)
        print(f"Alpha Warrior — {datetime.now().strftime('%d-%b-%Y %H:%M')}")
        print("=" * 50)

        # Login
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
            f"🔍 Checking market mode..."
        )

        # Get market mode
        mode = get_market_mode()

        if mode is None:
            send_telegram_message(
                f"😴 Market too weak ({datetime.now().strftime('%d-%b-%Y')})\n"
                f"Nifty below SMA200\n"
                f"No trades today. See you tomorrow! 🕐"
            )
            return

        # Set mode specific settings
        if mode == "BULL":
            capital_per_trade = BULL_CAPITAL_PER_TRADE
            max_positions = BULL_MAX_POSITIONS
            min_score = BULL_MIN_SCORE
        else:  # HUNT
            capital_per_trade = HUNT_CAPITAL_PER_TRADE
            max_positions = HUNT_MAX_POSITIONS
            min_score = HUNT_MIN_SCORE

        # Capital check
        available = get_available_capital()
        open_count = get_open_position_count()

        print(f"Mode: {mode}")
        print(f"Available capital: ₹{available:,.0f}")
        print(f"Open positions: {open_count}/{max_positions}")
        print(f"Capital per trade: ₹{capital_per_trade:,.0f}")

        # Send mode notification
        send_telegram_message(
            f"{'🚀 BULL MODE ACTIVE!' if mode == 'BULL' else '🎯 HUNT MODE ACTIVE!'}\n"
            f"Capital per trade: ₹{capital_per_trade:,.0f}\n"
            f"Max positions: {max_positions}\n"
            f"Available: ₹{available:,.0f}\n"
            f"Open positions: {open_count}/{max_positions}"
        )

        if available < capital_per_trade:
            msg = (
                f"⚠️ Insufficient capital!\n"
                f"Available: ₹{available:,.0f}\n"
                f"Need: ₹{capital_per_trade:,.0f}\n"
                f"Waiting for position to close..."
            )
            print(msg)
            send_telegram_message(msg)
            return

        if open_count >= max_positions:
            msg = (
                f"⚠️ Max positions reached!\n"
                f"Open: {open_count}/{max_positions}\n"
                f"Waiting for exit before new trade..."
            )
            print(msg)
            send_telegram_message(msg)
            return

        # Scan stocks
        symbols = [entry["symbol"] for entry in nse_tokens]
        print(f"Scanning {len(symbols)} symbols in {mode} mode...")
        tech_data = fetch_technical_data(symbols)
        print(f"Technical data fetched: {len(tech_data)}")

        # Apply mode-aware filters
        filtered = [s for s in tech_data if hybrid_filters(s, mode)]
        print(f"Stocks after {mode} filter: {len(filtered)}")

        if not filtered:
            print("No stocks matched today.")
            send_telegram_message(
                f"ℹ️ No stocks matched {mode} filters today\n"
                f"({datetime.now().strftime('%d-%b-%Y')})"
            )
            return

        scored = [score_stock(s) for s in filtered]
        high_quality = [s for s in scored if s["score"] >= min_score]
        print(f"Stocks with score >= {min_score}: {len(high_quality)}")

        if not high_quality:
            send_telegram_message(
                f"ℹ️ No stocks scored >= {min_score} today\n"
                f"Mode: {mode} — no quality setups"
            )
            return

        ranked = sorted(high_quality, key=lambda x: x["score"], reverse=True)
        fresh_picks = [s for s in ranked if not was_recently_alerted(s["symbol"])]

        if not fresh_picks:
            send_telegram_message(
                f"ℹ️ All top picks alerted within {COOLDOWN_DAYS} days\n"
                f"No new trades today"
            )
            return

        slots_available = max_positions - open_count
        top_stocks = fresh_picks[:min(TOP_N, slots_available)]

        for stock in top_stocks:
            symbol = stock["symbol"]
            price = stock["price"]
            send_telegram_alert(stock, mode)
            mark_as_alerted(symbol)
            print(f"✅ Alert sent for {symbol} (Score: {stock['score']}, Mode: {mode})")
            print(f"🔵 Initiating auto buy for {symbol} — ₹{capital_per_trade:,.0f}...")
            time.sleep(3)
            success = auto_buy(symbol, price, capital_per_trade, mode)
            if success:
                print(f"✅ Auto buy successful for {symbol}")
            else:
                print(f"❌ Auto buy failed for {symbol}")
                send_telegram_message(f"❌ Auto buy FAILED for {symbol}!")

        print(f"\nDone! Processed {len(top_stocks)} stock(s) in {mode} mode.")

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
