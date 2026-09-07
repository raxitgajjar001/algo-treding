import time
from typing import Dict, List, Tuple
from config import get_settings

class RiskManager:
    def __init__(self):
        self.emergency_halt = False

    def can_open_trade(
        self,
        account: Dict,
        open_trades: List[Dict],
        daily_realized_pnl: float
    ) -> Tuple[bool, str]:
        settings = get_settings()

        if self.emergency_halt:
            return False, "Emergency Halt is active."

        # 1. Check Max Daily Loss Limit
        max_daily_loss = float(account.get("max_loss_limit", settings.get("max_daily_loss", 2000.0)))
        if daily_realized_pnl <= -abs(max_daily_loss):
            return False, f"Daily loss limit reached (₹{abs(daily_realized_pnl)} / ₹{max_daily_loss}). Trading stopped for today to protect capital."

        # 2. Check Max Concurrent Trades for this account
        acc_open = [t for t in open_trades if t.get("account_id") == account["id"]]
        max_trades = settings.get("max_concurrent_trades", 5)
        if len(acc_open) >= max_trades:
            return False, f"Account {account['name']} reached max concurrent trades limit ({max_trades})."

        return True, "Approved"

    def calculate_position_size(self, account: Dict, entry_price: float) -> Tuple[int, float]:
        """
        Returns: (quantity, allocated_capital_rupees)
        Strictly applies the user's chosen percentage of capital.
        """
        if entry_price <= 0:
            return 0, 0.0

        total_capital = float(account.get("total_capital", 100000.0))
        allocation_pct = float(account.get("capital_allocation_pct", 10.0))

        # Example: ₹100,000 * 10% = ₹10,000 max allocation
        max_rupees = total_capital * (allocation_pct / 100.0)

        qty = int(max_rupees // entry_price)
        if qty < 1 and max_rupees >= entry_price:
            qty = 1

        actual_allocated = round(qty * entry_price, 2)
        return qty, actual_allocated

    def update_trailing_stoploss(self, trade: Dict, current_price: float) -> Tuple[float, float]:
        """
        Dynamically adjusts stop loss upward as trade moves into profit (Trailing Stop Loss).
        Guarantees that profits are locked in and prevents premature fakeout exits.
        Returns: (updated_trailing_sl, peak_price)
        """
        entry_price = float(trade["entry_price"])
        base_sl = float(trade.get("stoploss_price", entry_price * 0.975))
        current_trailing_sl = float(trade.get("trailing_sl_price", base_sl))
        peak_price = max(float(trade.get("peak_price", entry_price)), current_price)

        # Dynamic profit percentage from entry
        peak_gain_pct = ((peak_price - entry_price) / entry_price) * 100.0

        # Smart Trailing Rules:
        # 1. Once trade reaches +1.5% profit: Move SL to Cost + 0.2% (Breakeven - Risk Free Guarantee)
        if peak_gain_pct >= 1.5:
            cost_protected_sl = round(entry_price * 1.002, 2)
            current_trailing_sl = max(current_trailing_sl, cost_protected_sl)

        # 2. Once trade reaches +3.0% profit: Trail SL to lock in at least +1.8% profit
        if peak_gain_pct >= 3.0:
            lock_profit_sl = round(entry_price * 1.018, 2)
            current_trailing_sl = max(current_trailing_sl, lock_profit_sl)

        # 3. For large runners (>+4%): Trail behind peak by 1.5%
        if peak_gain_pct >= 4.0:
            trailing_margin_sl = round(peak_price * 0.985, 2)
            current_trailing_sl = max(current_trailing_sl, trailing_margin_sl)

        return current_trailing_sl, peak_price

    def should_exit_trade(self, trade: Dict, current_price: float) -> Tuple[bool, str]:
        """
        Evaluates Target, Dynamic Trailing Stop-Loss, Intraday Cutoff, or Swing Expiry.
        Includes market volatility wick buffer to prevent fakeout stopouts.
        """
        entry_price = float(trade["entry_price"])
        target_price = float(trade["target_price"])
        trade_type = trade.get("trade_type", "INTRADAY")
        entry_timestamp = float(trade.get("entry_time", time.time()))

        # Update Trailing Stop Loss & Peak Price
        trailing_sl, peak_price = self.update_trailing_stoploss(trade, current_price)
        trade["trailing_sl_price"] = trailing_sl
        trade["peak_price"] = peak_price

        # 1. Target Hit (Full Profit Booking)
        if current_price >= target_price:
            pnl = round((current_price - entry_price) * trade["qty"], 2)
            return True, f"TARGET_HIT (ટાર્ગેટ હિટ: +₹{pnl})"

        # 2. Dynamic Trailing Stop-Loss Hit
        # If price was in profit and pulled back to trailing SL -> Profit Locked Exit
        if current_price <= trailing_sl:
            pnl = round((current_price - entry_price) * trade["qty"], 2)
            if trailing_sl > entry_price:
                return True, f"TRAILING_SL_PROFIT_LOCKED (પ્રોફિટ સુરક્ષિત એક્ઝિટ: +₹{pnl})"
            else:
                # Volatility buffer check: Avoid panic sell on momentary 0.25% noise wick
                # Only exit if confirmed below stoploss level
                wick_buffer = entry_price * 0.0025
                if current_price <= (trailing_sl - wick_buffer):
                    return True, f"STOPLOSS_HIT (રક્ષણાત્મક એક્ઝિટ: -₹{abs(pnl)})"

        # 3. Intraday Auto Square-off (Time check: 15:15 IST)
        if trade_type == "INTRADAY":
            current_time_str = time.strftime("%H:%M")
            if current_time_str >= "15:15":
                pnl = round((current_price - entry_price) * trade["qty"], 2)
                return True, f"INTRADAY_315_SQUAREOFF (૩:૧૫ માર્કેટ ક્લોઝિંગ એક્ઝિટ: ₹{pnl})"

        # 4. Swing 7-Day Time-Stop
        if trade_type == "SWING_DELIVERY":
            elapsed_days = (time.time() - entry_timestamp) / 86400.0
            if elapsed_days >= 7.0:
                pnl = round((current_price - entry_price) * trade["qty"], 2)
                return True, f"SWING_7DAY_TIMESTOP (૭ દિવસ એક્સ્પાયરી: ₹{pnl})"

        return False, "HOLD"
