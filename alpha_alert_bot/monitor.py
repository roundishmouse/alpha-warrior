import os
import time
import pyotp
from datetime import datetime, timedelta
from SmartApi.smartConnect import SmartConnect
from dotenv import load_dotenv
from trade_manager import (
    load_positions, save_positions, auto_sell,
    get_angel_one_session, get_live_price, send_telegram
)

load_dotenv()

# ============================================================
# CONFIGURATION
# ============================================================
STOP_LOSS_PCT = 0.08        # -8%
TARGET_PCT = 0.20           # +20%
QUICK_MOVE_WEEKS = 3        # Weeks to consider a "quick move"
MAX_HOLD_WEEKS = 8          # Maximum hold period


# ============================================================
# CHECK IF MARKET IS OPEN
# ============================================================
def is_market_open():
    now = datetime.now()
    # Monday to Friday only
    if now.weekday() >= 5:
        return False
    # 9:15 AM to 3:25 PM
    market_open = now.replace(hour=9, minute=15, second=0)
    market_close = now.replace(hour=15, minute=25, second=0)
    return market_open <= now <= market_close


# ============================================================
# MONITOR ALL OPEN POSITIONS
# ============================================================
def monitor_positions():
    if not is_market_open():
        print("Market is closed. Nothing to monitor.")
        return

    data = load_positions()
    open_positions = data["open_positions"]

    if not open_positions:
        print("No open positions to monitor.")
        return

    print(f"\n{'='*50}")
    print(f"📊 Monitoring {len(open_positions)} position(s) — {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*50}")

    # Login once for all positions
    obj = get_angel_one_session()
    if not obj:
        print("❌ Could not login to Angel One")
        return

    for position in open_positions[:]:  # Copy to avoid mutation during iteration
        symbol = position["symbol"]
        token = position["token"]
        buy_price = position["buy_price"]
        buy_date = datetime.strptime(position["buy_date"], "%Y-%m-%d")
        quantity = position["quantity"]

        # Get live price
        live_price = get_live_price(obj, symbol, token)
        if not live_price:
            print(f"⚠️ Could not get price for {symbol} — skipping")
            continue

        # Calculate current P&L
        pnl_pct = ((live_price - buy_price) / buy_price) * 100
        pnl_amount = (live_price - buy_price) * quantity
        days_held = (datetime.now() - buy_date).days
        weeks_held = days_held / 7

        print(f"\n{symbol}:")
        print(f"  Buy: ₹{buy_price} | Now: ₹{live_price}")
        print(f"  P&L: ₹{pnl_amount:,.0f} ({pnl_pct:.2f}%)")
        print(f"  Days held: {days_held} | Weeks: {weeks_held:.1f}")

        # ── RULE 1: STOP LOSS -8% ──
        if pnl_pct <= -STOP_LOSS_PCT * 100:
            print(f"  🔴 STOP LOSS triggered at {pnl_pct:.2f}%")
            auto_sell(position, f"Stop Loss (-8%) hit at ₹{live_price}")
            continue

        # ── RULE 2: TARGET +20% HIT ──
        if pnl_pct >= TARGET_PCT * 100:

            # Check if quick move (< 3 weeks)
            if weeks_held < QUICK_MOVE_WEEKS:

                # First time hitting +20% quickly
                if not position.get("quick_move"):
                    hold_till = buy_date + timedelta(weeks=MAX_HOLD_WEEKS)
                    position["quick_move"] = True
                    position["hold_till"] = hold_till.strftime("%Y-%m-%d")

                    # Update in positions file
                    data = load_positions()
                    for p in data["open_positions"]:
                        if p["symbol"] == symbol:
                            p["quick_move"] = True
                            p["hold_till"] = hold_till.strftime("%Y-%m-%d")
                    save_positions(data)

                    msg = (
                        f"🚀 QUICK MOVE DETECTED — {symbol}\n"
                        f"Hit +{pnl_pct:.1f}% in {weeks_held:.1f} weeks!\n"
                        f"O'Neil Rule: HOLDING for 8 weeks\n"
                        f"Hold till: {hold_till.strftime('%d-%b-%Y')}\n"
                        f"Current P&L: ₹{pnl_amount:,.0f}"
                    )
                    send_telegram(msg)
                    print(f"  🚀 Quick move! Holding till {hold_till.strftime('%d-%b-%Y')}")

                else:
                    # Already flagged as quick move — check if 8 weeks done
                    hold_till = datetime.strptime(position["hold_till"], "%Y-%m-%d")
                    if datetime.now() >= hold_till:
                        print(f"  ⏰ 8 weeks complete — selling!")
                        auto_sell(position, f"8-week hold complete. Final P&L: {pnl_pct:.1f}%")
                    else:
                        days_left = (hold_till - datetime.now()).days
                        print(f"  🚀 Holding — {days_left} days left till 8 weeks")

            else:
                # +20% achieved but took more than 3 weeks — sell now
                print(f"  🟢 Target +20% hit after {weeks_held:.1f} weeks — selling!")
                auto_sell(position, f"Target +20% hit at ₹{live_price} after {weeks_held:.1f} weeks")
            continue

        # ── RULE 3: MAX 8 WEEKS HOLD ──
        if weeks_held >= MAX_HOLD_WEEKS:
            print(f"  ⏰ Max hold period (8 weeks) reached — selling!")
            auto_sell(position, f"8-week maximum hold reached. P&L: {pnl_pct:.1f}%")
            continue

        # All good — still holding
        print(f"  ✅ Holding — {MAX_HOLD_WEEKS - weeks_held:.1f} weeks remaining")


# ============================================================
# ENTRY POINT
# ============================================================
if __name__ == "__main__":
    monitor_positions()
