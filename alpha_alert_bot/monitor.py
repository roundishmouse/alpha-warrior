import os
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
from trade_manager import (
    load_positions, save_positions, auto_sell,
    get_angel_one_session, get_live_price, send_telegram
)

load_dotenv()

TARGET_PCT = 0.20
QUICK_MOVE_WEEKS = 3
MAX_HOLD_WEEKS = 8


def is_market_open():
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    market_open = now.replace(hour=9, minute=15, second=0)
    market_close = now.replace(hour=15, minute=25, second=0)
    return market_open <= now <= market_close


def monitor_positions():
    if not is_market_open():
        print("Market closed. Nothing to monitor.")
        return

    data = load_positions()
    open_positions = data["open_positions"]

    if not open_positions:
        print("No open positions.")
        return

    print(f"\n{'='*50}")
    print(f"📊 Monitoring {len(open_positions)} position(s) — {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*50}")

    obj = get_angel_one_session()
    if not obj:
        return

    for position in open_positions[:]:
        symbol = position["symbol"]
        token = position["token"]
        buy_price = position["buy_price"]
        buy_date = datetime.strptime(position["buy_date"], "%Y-%m-%d")
        quantity = position["quantity"]
        mode = position.get("mode", "BULL")

        # Get mode specific stop loss
        stop_loss_pct = position.get("stop_loss_pct", 0.08)

        live_price = get_live_price(obj, symbol, token)
        if not live_price:
            continue

        pnl_pct = ((live_price - buy_price) / buy_price) * 100
        pnl_amount = (live_price - buy_price) * quantity
        days_held = (datetime.now() - buy_date).days
        weeks_held = days_held / 7

        mode_emoji = "🚀" if mode == "BULL" else "🎯"
        print(f"\n{mode_emoji} [{mode}] {symbol}:")
        print(f"  Buy: ₹{buy_price} | Now: ₹{live_price}")
        print(f"  P&L: ₹{pnl_amount:,.0f} ({pnl_pct:.2f}%)")
        print(f"  Stop loss: -{int(stop_loss_pct*100)}% | Days: {days_held}")

        # RULE 1: STOP LOSS
        if pnl_pct <= -(stop_loss_pct * 100):
            print(f"  🔴 STOP LOSS triggered!")
            auto_sell(position, f"Stop Loss (-{int(stop_loss_pct*100)}%) at ₹{live_price}")
            continue

        # RULE 2: TARGET +20%
        if pnl_pct >= TARGET_PCT * 100:
            if weeks_held < QUICK_MOVE_WEEKS:
                if not position.get("quick_move"):
                    hold_till = buy_date + timedelta(weeks=MAX_HOLD_WEEKS)
                    position["quick_move"] = True
                    position["hold_till"] = hold_till.strftime("%Y-%m-%d")

                    data = load_positions()
                    for p in data["open_positions"]:
                        if p["symbol"] == symbol:
                            p["quick_move"] = True
                            p["hold_till"] = hold_till.strftime("%Y-%m-%d")
                    save_positions(data)

                    msg = (
                        f"🚀 QUICK MOVE [{mode}] — {symbol}\n"
                        f"+{pnl_pct:.1f}% in {weeks_held:.1f} weeks!\n"
                        f"O'Neil Rule: HOLDING 8 weeks\n"
                        f"Hold till: {hold_till.strftime('%d-%b-%Y')}\n"
                        f"P&L: ₹{pnl_amount:,.0f}"
                    )
                    send_telegram(msg)
                else:
                    hold_till = datetime.strptime(position["hold_till"], "%Y-%m-%d")
                    if datetime.now() >= hold_till:
                        auto_sell(position, f"8-week hold complete. P&L: {pnl_pct:.1f}%")
                    else:
                        days_left = (hold_till - datetime.now()).days
                        print(f"  🚀 Holding — {days_left} days left")
            else:
                auto_sell(position, f"Target +20% after {weeks_held:.1f} weeks at ₹{live_price}")
            continue

        # RULE 3: MAX 8 WEEKS
        if weeks_held >= MAX_HOLD_WEEKS:
            auto_sell(position, f"8-week max hold. P&L: {pnl_pct:.1f}%")
            continue

        print(f"  ✅ Holding — {MAX_HOLD_WEEKS - weeks_held:.1f} weeks left")


if __name__ == "__main__":
    monitor_positions()
