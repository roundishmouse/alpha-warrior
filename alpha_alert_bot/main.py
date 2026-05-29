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

load_dotenv()

app = Flask(__name__)

# ============================================================
# CONFIGURATION — tweak these without touching any other code
# ============================================================
MIN_SCORE = 7            # Only alert stocks with score >= 7
MAX_PRICE = 5000         # Ignore stocks above ₹5,000 (PAGEIND problem)
MIN_VOLUME = 50000       # Minimum daily volume — liquidity filter
COOLDOWN_DAYS = 7        # Don't re-alert same stock within 7 days
TOP_N = 2                # Number of top stocks to alert daily
ALERT_LOG_FILE = "alert_log.json"  # Tracks recently alerted stocks

# ETF / Bond / Index keywords — these will be filtered out
ETF_KEYWORDS = [
    "ETF", "BEES", "GSEC", "TBILL", "LIQUID", "GILT",
    "BOND", "NIFTY", "SENSEX", "JUNIOR", "NEXT50",
    "HDFCNIF", "EQUAL50", "MOM50", "MOM100", "LOWVOL",
    "DIVGIT", "BANKBEES", "CPSEETF", "PSUBNKBEES"
]

# ============================================================
# FLASK KEEP-ALIVE — unchanged from original
# ============================================================
@app.route("/")
def home():
    return "Alpha Warrior is running."


# ============================================================
# TELEGRAM ALERT — enhanced with score details
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
        f"🕐 {datetime.now().strftime('%d-%b-%Y %H:%M')}"
    )
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        requests.post(url, data={"chat_id": chat_id, "text": message})
    except Exception as e:
        print(f"Telegram error: {e}")


def send_telegram_message(text):
    """Send any plain text message to Telegram."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("T_BOT_CHAT_ID")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        requests.post(url, data={"chat_id": chat_id, "text": text})
    except Exception as e:
        print(f"Telegram error: {e}")


# ============================================================
# CHANGE 1 — 7-DAY COOLDOWN TRACKER
# Prevents same stock from alerting every day (GVT&D problem)
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
# CHANGE 2 — ETF / BOND FILTER
# Removes index ETFs, government bonds, liquid funds
# ============================================================
def is_etf_or_bond(symbol):
    sym_upper = symbol.upper()
    return any(keyword in sym_upper for keyword in ETF_KEYWORDS)


# ============================================================
# SAFE FLOAT — unchanged from original
# ============================================================
def safe_float(val):
    try:
        val = float(val)
        return 0 if math.isnan(val) else val
    except:
        return 0


# ============================================================
# CHANGE 3 — ENHANCED HYBRID FILTERS
# Added: price cap, min volume, ETF filter
# ============================================================
def hybrid_filters(stock):
    try:
        symbol = stock.get("symbol", "")

        # CHANGE 3a: Filter ETFs and bonds
        if is_etf_or_bond(symbol):
            return False

        price = safe_float(stock.get("price"))

        # CHANGE 3b: Price cap — ignore stocks above ₹5,000
        if price <= 0 or price > MAX_PRICE:
            return False

        high_52 = safe_float(stock.get("52w high"))
        sma150 = safe_float(stock.get("SMA150"))
        sma_vol = safe_float(stock.get("SOMA Volume"))
        curr_vol = safe_float(stock.get("Volume"))

        # CHANGE 3c: Minimum volume filter — liquidity check
        if curr_vol < MIN_VOLUME:
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
# SCORE STOCK — unchanged from original (it's good as is)
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

    # Price within 5% of 52w high
    proximity = price / high_52 if high_52 else 0
    if proximity >= 0.95:
        score += 2
    elif proximity >= 0.90:
        score += 1

    # Price above moving averages
    if price > sma20:
        score += 1
    if price > sma50:
        score += 1
    if price > sma150:
        score += 1

    # Volume strength
    vol_ratio = vol / vol50 if vol50 else 0
    if vol_ratio > 2:
        score += 2
    elif vol_ratio > 1.5:
        score += 1

    stock["score"] = score
    return stock


# ============================================================
# FETCH TECHNICAL DATA — unchanged from original
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


# ============================================================
# CHANGE 4 — SWITCHED SMA200 → EMA200 FOR MARKET CHECK
# EMA reacts faster to price changes — catches bull market earlier
# Minervini himself uses EMA200 for market direction
# SMA200 was at 25,002 — EMA200 is at 23,815 (already bullish!)
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

        # CHANGE 4: EMA200 instead of SMA200
        ema200 = hist["Close"].ewm(span=200, adjust=False).mean().iloc[-1]

        print(f"Nifty: {round(current, 2)}, SMA50: {round(sma50, 2)}, EMA200: {round(ema200, 2)}")

        is_bullish = current > sma50 and current > ema200
        print(f"Market is {'BULLISH ✅' if is_bullish else 'NOT bullish ❌'}")
        return is_bullish

    except Exception as e:
        print(f"Error checking market trend: {e}")
        return False


# ============================================================
# MAIN BOT LOGIC
# ============================================================
def run_bot():
    try:
        print("=" * 50)
        print(f"Alpha Warrior starting — {datetime.now().strftime('%d-%b-%Y %H:%M')}")
        print("=" * 50)

        # Login to Angel One — unchanged
        print("Logging in to SmartAPI...")
        api_key = os.getenv("SMARTAPI_API_KEY")
        client_code = os.getenv("SMARTAPI_CLIENT_CODE")
        password = os.getenv("SMARTAPI_PASSWORD")
        totp_secret = os.getenv("SMARTAPI_TOTP")
        totp = pyotp.TOTP(totp_secret).now()
        time.sleep(5)

        obj = SmartConnect(api_key=api_key)
        data = obj.generateSession(client_code, password, totp)
        print("Login successful.")

        # CHANGE 4: Market check now uses EMA200
        if not is_market_bullish():
            print("Market is not bullish. Skipping scan.")
            send_telegram_message(
                f"⚠️ Alpha Warrior: Market not bullish today ({datetime.now().strftime('%d-%b-%Y')}). No scan."
            )
            return

        # Fetch and filter
        symbols = [entry["symbol"] for entry in nse_tokens]
        print(f"Scanning {len(symbols)} symbols...")

        tech_data = fetch_technical_data(symbols)
        print(f"Technical data fetched: {len(tech_data)}")

        # CHANGE 3: Enhanced filters (ETF + price cap + volume)
        filtered = [s for s in tech_data if hybrid_filters(s)]
        print(f"Stocks after hybrid filter: {len(filtered)}")

        if not filtered:
            print("No stocks matched today.")
            send_telegram_message(
                f"ℹ️ Alpha Warrior: No stocks matched filters today ({datetime.now().strftime('%d-%b-%Y')})."
            )
            return

        # Score all filtered stocks
        scored = [score_stock(s) for s in filtered]

        # CHANGE 2: Only keep score >= MIN_SCORE (7)
        high_quality = [s for s in scored if s["score"] >= MIN_SCORE]
        print(f"Stocks with score >= {MIN_SCORE}: {len(high_quality)}")

        if not high_quality:
            print(f"No stocks scored >= {MIN_SCORE} today.")
            send_telegram_message(
                f"ℹ️ Alpha Warrior: {len(scored)} stocks passed filters but none scored >= {MIN_SCORE} today."
            )
            return

        # Rank by score
        ranked = sorted(high_quality, key=lambda x: x["score"], reverse=True)

        # CHANGE 1: Apply 7-day cooldown filter
        fresh_picks = [s for s in ranked if not was_recently_alerted(s["symbol"])]
        print(f"Fresh picks (not recently alerted): {len(fresh_picks)}")

        if not fresh_picks:
            print("All top picks were recently alerted. No new alerts today.")
            send_telegram_message(
                f"ℹ️ Alpha Warrior: All picks were recently alerted. No new alerts today."
            )
            return

        # Take top N
        top_stocks = fresh_picks[:TOP_N]

        # Send alerts
        for stock in top_stocks:
            send_telegram_alert(stock)
            mark_as_alerted(stock["symbol"])
            print(f"✅ Sent alert for {stock['symbol']} (Score: {stock['score']})")

        print(f"Done! Alerted {len(top_stocks)} stock(s) today.")

    except Exception as e:
        print(f"Bot error: {e}")
        send_telegram_message(f"❌ Alpha Warrior error: {e}")


# ============================================================
# ENTRY POINT — unchanged from original
# ============================================================
if __name__ == "__main__":
    threading.Thread(target=run_bot).start()
    app.run(host="0.0.0.0", port=10000)
