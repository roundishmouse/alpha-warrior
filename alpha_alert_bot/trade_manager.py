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
# CONFIGURATION — All settings in one place
# ============================================================
CAPITAL_PER_TRADE = 50000       # ₹50,000 per trade
MAX_POSITIONS = 3               # Maximum 3 open positions at once
STOP_LOSS_PCT = 0.08            # -8% stop loss (O'Neil rule)
TARGET_PCT = 0.20               # +20% profit target
QUICK_MOVE_WEEKS = 3            # If +20% within 3 weeks → hold 8 weeks
MAX_HOLD_WEEKS = 8              # Maximum hold period (O'Neil rule)
POSITIONS_FILE = "positions.json"
EXCHANGE = "NSE"
PRODUCT_TYPE = "DELIVERY"       # CNC — hold for weeks/months
ORDER_TYPE = "MARKET"           # Market order for instant execution


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
        print(f"❌ Angel One login failed: {e}")
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
# Reads and writes positions.json
# ============================================================
def load_positions():
    try:
        with open(POSITIONS_FILE, "r") as f:
            return json.load(f)
    except:
        # First time — create fresh positions file
        default = {
            "available_capital": 149633,
            "deployed_capital": 0,
            "open_positions": [],
            "closed_positions": [],
            "total_realized_pnl": 0
        }
        save_positions(default)
        return default


def save_positions(data):
    try:
        with open(POSITIONS_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error saving positions: {e}")


def get_open_position_count():
    data = load_positions()
    return len(data["open_positions"])


def get_available_capital():
    data = load_positions()
    return data["available_capital"]


# ============================================================
# GET TOKEN FOR SYMBOL
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
        print(f"Error getting LTP for {symbol}: {e}")
        return None


# ============================================================
# AUTO BUY
# ============================================================
def auto_buy(symbol, alert_price):
    print(f"\n{'='*50}")
    print(f"🔵 AUTO BUY triggered for {symbol}")
    print(f"{'='*50}")

    # Check available capital
    available = get_available_capital()
    if available < CAPITAL_PER_TRADE:
        msg = f"⚠️ Insufficient capital for {symbol}. Available: ₹{available:,.0f}"
        print(msg)
        send_telegram(msg)
        return False

    # Check max positions
    open_count = get_open_position_count()
    if open_count >= MAX_POSITIONS:
        msg = f"⚠️ Max positions ({MAX_POSITIONS}) reached. Cannot buy {symbol}."
        print(msg)
        send_telegram(msg)
        return False

    # Get token
    token = get_token_for_symbol(symbol)
    if not token:
        print(f"❌ Token not found for {symbol}")
        return False

    # Login
    obj = get_angel_one_session()
    if not obj:
        return False

    # Get live price
    live_price = get_live_price(obj, symbol, token)
    if not live_price:
        print(f"❌ Could not get live price for {symbol}")
        return False

    # Calculate quantity
    quantity = int(CAPITAL_PER_TRADE / live_price)
    if quantity < 1:
        print(f"❌ Cannot buy even 1 share of {symbol} at ₹{live_price}")
        return False

    actual_amount = quantity * live_price
    stop_loss_price = round(live_price * (1 - STOP_LOSS_PCT), 2)
    target_price = round(live_price * (1 + TARGET_PCT), 2)

    print(f"Symbol: {symbol}")
    print(f"Live Price: ₹{live_price}")
    print(f"Quantity: {quantity}")
    print(f"Amount: ₹{actual_amount:,.0f}")
    print(f"Stop Loss: ₹{stop_loss_price} (-8%)")
    print(f"Target: ₹{target_price} (+20%)")

    # Place buy order
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
        print(f"✅ Buy order placed! Order ID: {order_id}")

        # Save position
        data = load_positions()
        position = {
            "symbol": symbol,
            "token": token,
            "buy_price": live_price,
            "quantity": quantity,
            "amount_invested": actual_amount,
            "stop_loss": stop_loss_price,
            "target": target_price,
            "buy_date": datetime.now().strftime("%Y-%m-%d"),
            "buy_time": datetime.now().strftime("%H:%M:%S"),
            "order_id": order_id,
            "status": "OPEN",
            "quick_move": False,        # Will be set True if +20% in < 3 weeks
            "hold_till": None           # Will be set if quick move detected
        }
        data["open_positions"].append(position)
        data["available_capital"] -= actual_amount
        data["deployed_capital"] += actual_amount
        save_positions(data)

        # Telegram notification
        msg = (
            f"🟢 AUTO BUY EXECUTED!\n"
            f"Stock: {symbol}\n"
            f"Price: ₹{live_price}\n"
            f"Qty: {quantity} shares\n"
            f"Invested: ₹{actual_amount:,.0f}\n"
            f"Stop Loss: ₹{stop_loss_price} (-8%)\n"
            f"Target: ₹{target_price} (+20%)\n"
            f"Date: {datetime.now().strftime('%d-%b-%Y %H:%M')}\n"
            f"Capital Remaining: ₹{data['available_capital']:,.0f}"
        )
        send_telegram(msg)
        return True

    except Exception as e:
        error_msg = f"❌ Buy order FAILED for {symbol}: {e}"
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

    print(f"\n{'='*50}")
    print(f"🔴 AUTO SELL triggered for {symbol}")
    print(f"Reason: {reason}")
    print(f"{'='*50}")

    # Login
    obj = get_angel_one_session()
    if not obj:
        return False

    # Get live price
    live_price = get_live_price(obj, symbol, token)
    if not live_price:
        return False

    pnl = (live_price - buy_price) * quantity
    pnl_pct = ((live_price - buy_price) / buy_price) * 100

    print(f"Buy Price: ₹{buy_price}")
    print(f"Sell Price: ₹{live_price}")
    print(f"P&L: ₹{pnl:,.0f} ({pnl_pct:.2f}%)")

    # Place sell order
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
        print(f"✅ Sell order placed! Order ID: {order_id}")

        # Update positions
        data = load_positions()
        sell_amount = live_price * quantity

        # Move to closed positions
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

        # Telegram
        emoji = "🟢" if pnl > 0 else "🔴"
        msg = (
            f"{emoji} AUTO SELL EXECUTED!\n"
            f"Stock: {symbol}\n"
            f"Buy: ₹{buy_price} → Sell: ₹{live_price}\n"
            f"Qty: {quantity} shares\n"
            f"P&L: ₹{pnl:,.0f} ({pnl_pct:.2f}%)\n"
            f"Reason: {reason}\n"
            f"Date: {datetime.now().strftime('%d-%b-%Y %H:%M')}\n"
            f"Total Realized P&L: ₹{data['total_realized_pnl']:,.0f}\n"
            f"Available Capital: ₹{data['available_capital']:,.0f}"
        )
        send_telegram(msg)
        return True

    except Exception as e:
        error_msg = f"❌ Sell order FAILED for {symbol}: {e}"
        print(error_msg)
        send_telegram(error_msg)
        return False
