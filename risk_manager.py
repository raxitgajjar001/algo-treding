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

        # 1. Check Max Daily Portfolio Loss Limit (Strict 2% Circuit Breaker)
        total_capital = float(account.get("total_capital", 100000.0))
        two_pct_loss = total_capital * 0.02
        configured_loss = float(account.get("max_loss_limit", settings.get("max_daily_loss", 2000.0)))
        max_daily_loss = min(two_pct_loss, configured_loss) if configured_loss > 0 else two_pct_loss

        if daily_realized_pnl <= -abs(max_daily_loss):
            self.emergency_halt = True
            return False, f"Daily portfolio loss exceeded 2% risk circuit breaker (-₹{abs(daily_realized_pnl):,.2f} / ₹{max_daily_loss:,.2f}). Trading stopped for today to protect capital."

        # 2. Check 3 Consecutive Losses Limit
        if getattr(self, "consecutive_losses", 0) >= 3:
            return False, "3 consecutive losing trades reached today. Engine halted to preserve capital."

        # 3. Check Max Concurrent Trades for this account
        acc_open = [t for t in open_trades if t.get("account_id") == account["id"]]
        max_trades = settings.get("max_concurrent_trades", 5)
        if len(acc_open) >= max_trades:
            return False, f"Account {account['name']} reached max concurrent trades limit ({max_trades})."

        # 4. Strict Capital Allocation Pool Check (e.g. 25% across ALL active trades)
        alloc_pct = float(account.get("capital_allocation_pct", settings.get("capital_allocation_pct", 25.0)))
        max_pool = total_capital * (alloc_pct / 100.0)

        used_capital = sum(float(t.get("entry_price", 0.0)) * int(t.get("qty", 1)) for t in acc_open)
        if used_capital >= max_pool:
            return False, f"Max {alloc_pct}% Capital Pool (₹{max_pool:,.2f}) fully deployed across active trades. 75% remains protected."

        return True, "Approved"

    def calculate_position_size(
        self,
        account: Dict,
        entry_price: float,
        open_trades: List[Dict] = None
    ) -> Tuple[int, float]:
        """
        Returns: (quantity, allocated_capital_rupees)
        Strictly divides the user's chosen capital allocation pool (e.g. 25%)
        across active trades so total deployed capital NEVER exceeds the 25% pool.
        """
        if entry_price <= 0:
            return 0, 0.0

        if open_trades is None:
            open_trades = []

        settings = get_settings()
        total_capital = float(account.get("total_capital", 100000.0))
        alloc_pct = float(account.get("capital_allocation_pct", settings.get("capital_allocation_pct", 25.0)))
        max_pool = total_capital * (alloc_pct / 100.0)

        acc_open = [t for t in open_trades if t.get("account_id") == account["id"]]
        used_capital = sum(float(t.get("entry_price", 0.0)) * int(t.get("qty", 1)) for t in acc_open)
        remaining_pool = max(0.0, max_pool - used_capital)

        if remaining_pool <= 0:
            return 0, 0.0

        max_trades = settings.get("max_concurrent_trades", 5)
        remaining_slots = max(1, max_trades - len(acc_open))
        trade_budget = remaining_pool / remaining_slots

        qty = int(trade_budget // entry_price)
        if qty < 1 and remaining_pool >= entry_price:
            qty = 1

        # Hard cap: Never allow quantity to exceed remaining allocation pool
        if (qty * entry_price) > remaining_pool:
            qty = int(remaining_pool // entry_price)

        if qty <= 0:
            return 0, 0.0

        actual_allocated = round(qty * entry_price, 2)
        return qty, actual_allocated

    def update_trailing_stoploss(self, trade: Dict, current_price: float) -> Tuple[float, float]:
        """
        Dynamically adjusts stop loss as trade moves into profit for BOTH directions:
        - LONG (BUY): Trails upward as price rises to lock in profits.
        - SHORT (SELL): Trails downward as price falls to lock in downward profits.
        """
        direction = trade.get("direction", "BUY").upper()
        entry_price = float(trade["entry_price"])
        qty = int(trade.get("qty", 1))

        if direction in ["BUY", "BUY_CALL", "LONG"]:
            base_sl = float(trade.get("stoploss_price", entry_price * 0.991))
            current_trailing_sl = float(trade.get("trailing_sl_price", base_sl))
            peak_price = max(float(trade.get("peak_price", entry_price)), current_price)
            peak_gain_pct = ((peak_price - entry_price) / entry_price) * 100.0

            risk_unit = abs(entry_price - base_sl)

            # 0. Reach 1:1 Risk-Reward -> Move SL to Cost (Break-even guarantee)
            if risk_unit > 0 and peak_price >= (entry_price + risk_unit):
                cost_protected_sl = round(entry_price * 1.001, 2)
                current_trailing_sl = max(current_trailing_sl, cost_protected_sl)

            # 1. Reach +1.0% profit -> Move SL to Cost + 0.2% (Risk Free Guarantee)
            if peak_gain_pct >= 1.0:
                cost_protected_sl = round(entry_price * 1.002, 2)
                current_trailing_sl = max(current_trailing_sl, cost_protected_sl)

            # 2. Reach +2.0% profit -> Lock in at least +1.2% profit
            if peak_gain_pct >= 2.0:
                lock_profit_sl = round(entry_price * 1.012, 2)
                current_trailing_sl = max(current_trailing_sl, lock_profit_sl)

            # 3. Super-runner (>+3%) -> Trail behind peak by 1.0%
            if peak_gain_pct >= 3.0:
                trail_sl = round(peak_price * 0.99, 2)
                current_trailing_sl = max(current_trailing_sl, trail_sl)

            return current_trailing_sl, peak_price

        else:
            # SHORT / SELL (Market going DOWN)
            base_sl = float(trade.get("stoploss_price", entry_price * 1.009))
            current_trailing_sl = float(trade.get("trailing_sl_price", base_sl))
            trough_price = min(float(trade.get("peak_price", entry_price)), current_price)
            down_gain_pct = ((entry_price - trough_price) / entry_price) * 100.0

            risk_unit = abs(base_sl - entry_price)

            # 0. Reach 1:1 Risk-Reward -> Move SL to Cost (Break-even guarantee)
            if risk_unit > 0 and trough_price <= (entry_price - risk_unit):
                cost_protected_sl = round(entry_price * 0.999, 2)
                current_trailing_sl = min(current_trailing_sl, cost_protected_sl)

            # 1. Down +1.0% profit -> Move SL down to Cost - 0.2% (Risk Free Short)
            if down_gain_pct >= 1.0:
                cost_protected_sl = round(entry_price * 0.998, 2)
                current_trailing_sl = min(current_trailing_sl, cost_protected_sl)

            # 2. Down +2.0% profit -> Lock in at least +1.2% short profit
            if down_gain_pct >= 2.0:
                lock_profit_sl = round(entry_price * 0.988, 2)
                current_trailing_sl = min(current_trailing_sl, lock_profit_sl)

            # 3. Deep dive (>+3%) -> Trail above trough by 1.0%
            if down_gain_pct >= 3.0:
                trail_sl = round(trough_price * 1.01, 2)
                current_trailing_sl = min(current_trailing_sl, trail_sl)

            return current_trailing_sl, trough_price

    def should_exit_trade(self, trade: Dict, current_price: float) -> Tuple[bool, str]:
        """
        Evaluates Target, Trailing Stop-Loss, or 15:15 IST Intraday Cutoff.
        Handles both LONG (BUY) and SHORT (SELL) trades.
        """
        direction = trade.get("direction", "BUY").upper()
        entry_price = float(trade["entry_price"])
        target_price = float(trade["target_price"])
        qty = int(trade.get("qty", 1))

        # Update Trailing Stop Loss & Peak Price
        trailing_sl, peak_price = self.update_trailing_stoploss(trade, current_price)
        trade["trailing_sl_price"] = trailing_sl
        trade["peak_price"] = peak_price

        is_long = direction in ["BUY", "BUY_CALL", "LONG"]
        pnl = round((current_price - entry_price) * qty, 2) if is_long else round((entry_price - current_price) * qty, 2)

        # 1. Target Hit (Full Profit Booking)
        if (is_long and current_price >= target_price) or ((not is_long) and current_price <= target_price):
            return True, f"TARGET_HIT (ટાર્ગેટ હિટ: +₹{pnl})"

        # 2. Trailing Stop-Loss Hit
        if is_long and current_price <= trailing_sl:
            if trailing_sl > entry_price:
                return True, f"TRAILING_SL_PROFIT_LOCKED (પ્રોફિટ સુરક્ષિત એક્ઝિટ: +₹{pnl})"
            else:
                return True, f"STOPLOSS_HIT (રક્ષણાત્મક એક્ઝિટ: -₹{abs(pnl)})"
        elif (not is_long) and current_price >= trailing_sl:
            if trailing_sl < entry_price:
                return True, f"TRAILING_SL_PROFIT_LOCKED (પ્રોફિટ સુરક્ષિત એક્ઝિટ: +₹{pnl})"
            else:
                return True, f"STOPLOSS_HIT (રક્ષણાત્મક એક્ઝિટ: -₹{abs(pnl)})"

        # 3. Strict Intraday Auto Square-off (15:15 IST)
        current_time_str = time.strftime("%H:%M")
        if current_time_str >= "15:15":
            return True, f"INTRADAY_315_SQUAREOFF (૩:૧૫ માર્કેટ ક્લોઝિંગ એક્ઝિટ: ₹{pnl})"

        return False, "HOLD"

