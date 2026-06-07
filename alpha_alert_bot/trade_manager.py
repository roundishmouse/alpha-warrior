import os
import json
import requests
import pyotp
import time
from datetime import datetime, timedelta
from SmartApi.smartConnect import SmartConnect
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# CONFIGURATION
# ============================================================
POSITIONS_FILE = "positions.json"
EXCHANGE = "NSE"
PRODUCT_TYPE = "DELIVERY"
ORDER_TYPE = "MARKET"

# Stop loss per mode
STOP_LOSS = {
    "BULL": 0.08,   # -8% in bull mode
    "HUNT": 0.06,   # -6% in hunt mode (tighter!)
}

TARGET_PCT = 0.20           # +20% target both modes
QUICK_MOVE_WEEKS = 3
MAX_HOLD_WEEKS = 8


# ============================================================
# ANGEL ONE LOGIN
# ============================================================
def get_angel_one_session():
    try:
        api_key = os.getenv("SMARTAPI_API_KEY")
        client_code = os.getenv("SMARTAPI_CLIENT_CODE")
        password = os.getenv("SMARTAPI_PASSWORD")
        totp_secret = os.getenv("SMARTAPI_TOTP")
        totp = pyotp.TOTP(totp_secret).now()
        time.sleep(2)
        obj = SmartConnect(api_key=api_key)
        obj.generateSession(client_code, password, totp)
        print("✅ Angel One login successful")
        return obj
    except Exception as e:
        print(f"❌ Login failed: {e}")
        return None


# ============================================================
# TELEGRAM
# ============================================================
def send_telegram(message):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("T_BOT_CHAT_ID")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        requests.post(url, data={"chat_id": chat_id, "text": message})
    except Exception as e:
        print(f"Telegram error: {e}")


# ============================================================
# POSITIONS MANAGER
# ============================================================
def load_positions():
    try:
        with open(POSITIONS_FILE, "r") as f:
            return json.load(f)
    except:
        default = {
            "available_capital": 150976,
            "deployed_capital": 0,
            "open_positions": [],
            "closed_positions": [],
            "total_realized_pnl": 0,
            "bull_trades": 0,
            "hunt_trades": 0
        }
        save_positions(default)
        return default


def save_positions(data):
    try:
        with open(POSITIONS_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error saving: {e}")


def get_open_position_count():
    return len(load_positions()["open_positions"])


def get_available_capital():
    return load_positions()["available_capital"]


# ============================================================
# GET TOKEN
# ============================================================
def get_token_for_symbol(symbol):
    from nse_token_data_cleaned import nse_tokens
    for entry in nse_tokens:
        if entry["symbol"] == symbol:
            return entry["token"]
    return None


# ============================================================
# GET LIVE PRICE
# ============================================================
def get_live_price(obj, symbol, token):
    try:
        ltp_data = obj.ltpData(EXCHANGE, symbol, token)
        return float(ltp_data["data"]["ltp"])
    except Exception as e:
        print(f"Error getting LTP: {e}")
        return None


# ============================================================
# AUTO BUY — MODE AWARE
# ============================================================
def auto_buy(symbol, alert_price, capital_per_trade, mode="BULL"):
    print(f"\n{'='*50}")
    print(f"🔵 AUTO BUY [{mode} MODE] — {symbol}")
    print(f"{'='*50}")

    # Capital check
    available = get_available_capital()
    if available < capital_per_trade:
        msg = f"⚠️ Insufficient capital for {symbol}. Available: ₹{available:,.0f}"
        print(msg)
        send_telegram(msg)
        return False

    # Token
    token = get_token_for_symbol(symbol)
    if not token:
        print(f"❌ Token not found for {symbol}")
        return False

    # Login
    obj = get_angel_one_session()
    if not obj:
        return False

    # Live price
    live_price = get_live_price(obj, symbol, token)
    if not live_price:
        return False

    # Quantity
    quantity = int(capital_per_trade / live_price)
    if quantity < 1:
        print(f"❌ Cannot buy even 1 share at ₹{live_price}")
        return False

    actual_amount = quantity * live_price
    stop_loss_pct = STOP_LOSS.get(mode, 0.08)
    stop_loss_price = round(live_price * (1 - stop_loss_pct), 2)
    target_price = round(live_price * (1 + TARGET_PCT), 2)

    print(f"Mode: {mode}")
    print(f"Price: ₹{live_price}")
    print(f"Qty: {quantity}")
    print(f"Amount: ₹{actual_amount:,.0f}")
    print(f"Stop Loss: ₹{stop_loss_price} ({int(stop_loss_pct*100)}%)")
    print(f"Target: ₹{target_price} (+20%)")

    try:
        order_params = {
            "variety": "NORMAL",
            "tradingsymbol": symbol,
            "symboltoken": token,
            "transactiontype": "BUY",
            "exchange": EXCHANGE,
            "ordertype": ORDER_TYPE,
            "producttype": PRODUCT_TYPE,
            "duration": "DAY",
            "quantity": quantity
        }
        order_response = obj.placeOrder(order_params)
        order_id = order_response["data"]["orderid"]
        print(f"✅ Order placed! ID: {order_id}")

        # Save position
        data = load_positions()
        position = {
            "symbol": symbol,
            "token": token,
            "mode": mode,
            "buy_price": live_price,
            "quantity": quantity,
            "amount_invested": actual_amount,
            "stop_loss": stop_loss_price,
            "stop_loss_pct": stop_loss_pct,
            "target": target_price,
            "buy_date": datetime.now().strftime("%Y-%m-%d"),
            "buy_time": datetime.now().strftime("%H:%M:%S"),
            "order_id": order_id,
            "status": "OPEN",
            "quick_move": False,
            "hold_till": None
        }
        data["open_positions"].append(position)
        data["available_capital"] -= actual_amount
        data["deployed_capital"] += actual_amount

        # Track mode stats
        if mode == "BULL":
            data["bull_trades"] = data.get("bull_trades", 0) + 1
        else:
            data["hunt_trades"] = data.get("hunt_trades", 0) + 1

        save_positions(data)

        mode_emoji = "🚀" if mode == "BULL" else "🎯"
        msg = (
            f"{mode_emoji} AUTO BUY [{mode}] EXECUTED!\n"
            f"Stock: {symbol}\n"
            f"Price: ₹{live_price}\n"
            f"Qty: {quantity} shares\n"
            f"Invested: ₹{actual_amount:,.0f}\n"
            f"Stop Loss: ₹{stop_loss_price} (-{int(stop_loss_pct*100)}%)\n"
            f"Target: ₹{target_price} (+20%)\n"
            f"Date: {datetime.now().strftime('%d-%b-%Y %H:%M')}\n"
            f"Capital Remaining: ₹{data['available_capital']:,.0f}"
        )
        send_telegram(msg)
        return True

    except Exception as e:
        error_msg = f"❌ Buy FAILED for {symbol}: {e}"
        print(error_msg)
        send_telegram(error_msg)
        return False


# ============================================================
# AUTO SELL
# ============================================================
def auto_sell(position, reason):
    symbol = position["symbol"]
    token = position["token"]
    quantity = position["quantity"]
    buy_price = position["buy_price"]
    mode = position.get("mode", "BULL")

    print(f"\n{'='*50}")
    print(f"🔴 AUTO SELL [{mode}] — {symbol}")
    print(f"Reason: {reason}")
    print(f"{'='*50}")

    obj = get_angel_one_session()
    if not obj:
        return False

    live_price = get_live_price(obj, symbol, token)
    if not live_price:
        return False

    pnl = (live_price - buy_price) * quantity
    pnl_pct = ((live_price - buy_price) / buy_price) * 100

    try:
        order_params = {
            "variety": "NORMAL",
            "tradingsymbol": symbol,
            "symboltoken": token,
            "transactiontype": "SELL",
            "exchange": EXCHANGE,
            "ordertype": ORDER_TYPE,
            "producttype": PRODUCT_TYPE,
            "duration": "DAY",
            "quantity": quantity
        }
        order_response = obj.placeOrder(order_params)
        order_id = order_response["data"]["orderid"]

        # Update positions
        data = load_positions()
        sell_amount = live_price * quantity

        position["sell_price"] = live_price
        position["sell_date"] = datetime.now().strftime("%Y-%m-%d")
        position["sell_time"] = datetime.now().strftime("%H:%M:%S")
        position["sell_order_id"] = order_id
        position["pnl"] = round(pnl, 2)
        position["pnl_pct"] = round(pnl_pct, 2)
        position["exit_reason"] = reason
        position["status"] = "CLOSED"

        data["closed_positions"].append(position)
        data["open_positions"] = [
            p for p in data["open_positions"]
            if p["symbol"] != symbol
        ]
        data["available_capital"] += sell_amount
        data["deployed_capital"] -= position["amount_invested"]
        data["total_realized_pnl"] += round(pnl, 2)
        save_positions(data)

        emoji = "🟢" if pnl > 0 else "🔴"
        mode_emoji = "🚀" if mode == "BULL" else "🎯"
        msg = (
            f"{emoji} AUTO SELL [{mode}] EXECUTED!\n"
            f"Stock: {symbol}\n"
            f"Buy: ₹{buy_price} → Sell: ₹{live_price}\n"
            f"Qty: {quantity} shares\n"
            f"P&L: ₹{pnl:,.0f} ({pnl_pct:.2f}%)\n"
            f"Reason: {reason}\n"
            f"Date: {datetime.now().strftime('%d-%b-%Y %H:%M')}\n"
            f"Total P&L: ₹{data['total_realized_pnl']:,.0f}\n"
            f"Available: ₹{data['available_capital']:,.0f}\n"
            f"Bull trades: {data.get('bull_trades', 0)} | "
            f"Hunt trades: {data.get('hunt_trades', 0)}"
        )
        send_telegram(msg)
        return True

    except Exception as e:
        error_msg = f"❌ Sell FAILED for {symbol}: {e}"
        print(error_msg)
        send_telegram(error_msg)
        return False
