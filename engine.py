import time
import json
import uuid
from typing import List, Dict
from config import TRADES_FILE, get_settings
from account_manager import get_active_accounts
from indstocks_client import INDstocksClient
from risk_manager import RiskManager
from scanner import MarketScanner
from news_analyzer import fetch_rss_news

class TradingEngine:
    def __init__(self):
        self.risk_manager = RiskManager()
        self.scanner = MarketScanner()
        self.is_running = False
        self.active_trades: List[Dict] = []
        self.trade_history: List[Dict] = []
        self.daily_realized_pnl: float = 0.0
        self.logs: List[Dict] = []
        self.load_trades()

    def log(self, message: str, level: str = "INFO"):
        entry = {
            "timestamp": time.strftime("%H:%M:%S"),
            "level": level,
            "message": message
        }
        self.logs.insert(0, entry)
        if len(self.logs) > 100:
            self.logs = self.logs[:100]

    def load_trades(self):
        if TRADES_FILE.exists():
            try:
                with open(TRADES_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.active_trades = data.get("active", [])
                    self.trade_history = data.get("history", [])
                    self.daily_realized_pnl = sum(t.get("pnl", 0.0) for t in self.trade_history)
            except Exception:
                self.active_trades = []
                self.trade_history = []

    def save_trades(self):
        try:
            with open(TRADES_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "active": self.active_trades,
                    "history": self.trade_history,
                    "daily_realized_pnl": self.daily_realized_pnl
                }, f, indent=2)
        except Exception:
            pass

    def start(self) -> bool:
        if not self.is_indian_market_open():
            self.is_running = False
            self.log("બજાર બંધ હોવાથી ઓટો ટ્રેડિંગ શરૂ થઈ શકે નહીં (સવારે 09:15 થી બપોરે 03:30 દરમિયાન જ શરૂ થશે).", "WARNING")
            return False
        self.is_running = True
        self.risk_manager.emergency_halt = False
        self.log("Trading Engine Started (ઓટો ટ્રેડિંગ શરૂ થયું)", "SUCCESS")
        return True

    def stop(self):
        self.is_running = False
        self.log("Trading Engine Paused (ઓટો ટ્રેડિંગ થોભાવ્યું)", "WARNING")

    def execute_cycle(self):
        """Runs one full scan and execution iteration."""
        # 1. Update news feeds
        fetch_rss_news()

        # 2. STRICT CHECK: If market is closed, force engine OFF!
        if not self.is_indian_market_open():
            if self.is_running:
                self.is_running = False
                self.log("બજાર બંધ હોવાથી ઓટો ટ્રેડિંગ સંપૂર્ણપણે બંધ છે.", "INFO")
            return

        # 3. Monitor & evaluate active trades for Exit (Auto Sell)
        self.evaluate_active_trades()

        # 4. If engine is running, scan for new entries (Auto Buy)
        if self.is_running and not self.risk_manager.emergency_halt:
            self.evaluate_new_entries()

    def evaluate_active_trades(self):
        remaining_trades = []
        for trade in self.active_trades:
            # Find current price
            symbol = trade["symbol"]
            current_price = trade["entry_price"]
            for opp in self.scanner.cached_opportunities:
                if opp["symbol"] == symbol:
                    current_price = opp["current_price"]
                    break

            # Calculate live unrealized P&L
            qty = trade["qty"]
            unrealized_pnl = round((current_price - trade["entry_price"]) * qty, 2)
            trade["current_price"] = current_price
            trade["unrealized_pnl"] = unrealized_pnl
            trade["pnl_pct"] = round(((current_price - trade["entry_price"]) / trade["entry_price"]) * 100.0, 2)

            should_exit, reason = self.risk_manager.should_exit_trade(trade, current_price)
            if should_exit:
                self.close_trade(trade, current_price, reason)
            else:
                remaining_trades.append(trade)

        self.active_trades = remaining_trades
        self.save_trades()

    def is_indian_market_open(self) -> bool:
        """Indian stock exchange (NSE/BSE) trading hours: Mon-Fri, 09:15 AM to 03:30 PM IST."""
        import datetime
        utc_now = datetime.datetime.now(datetime.timezone.utc)
        ist_now = utc_now + datetime.timedelta(hours=5, minutes=30)
        weekday = ist_now.weekday()
        current_time = ist_now.time()
        market_open = datetime.time(9, 15)
        market_close = datetime.time(15, 30)
        return (weekday < 5) and (market_open <= current_time <= market_close)

    def evaluate_new_entries(self):
        # 1. Strictly verify Indian Market is OPEN! Zero new trades when market is closed!
        if not self.is_indian_market_open():
            return

        opportunities = self.scanner.scan_opportunities()
        high_score_opps = [o for o in opportunities if o["score"] >= 80]
        if not high_score_opps:
            return

        active_accounts = get_active_accounts()
        if not active_accounts:
            return

        # Pick top opportunity
        best_opp = high_score_opps[0]
        symbol = best_opp["symbol"]

        # Prevent duplicate entries for same symbol
        already_open_symbols = [t["symbol"] for t in self.active_trades]
        if symbol in already_open_symbols:
            return

        # Execute across all active accounts
        for acc in active_accounts:
            can_trade, reason = self.risk_manager.can_open_trade(
                account=acc,
                open_trades=self.active_trades,
                daily_realized_pnl=self.daily_realized_pnl
            )
            if not can_trade:
                self.log(f"Skipped {symbol} for {acc['name']}: {reason}", "INFO")
                continue

            # Calculate position size strictly per user-defined % of capital
            qty, allocated_funds = self.risk_manager.calculate_position_size(
                account=acc,
                entry_price=best_opp["current_price"]
            )
            if qty <= 0:
                continue

            settings = get_settings()
            global_mode = settings.get("mode", "PAPER")
            has_token = bool(acc.get("access_token", "").strip())
            is_live_order = (global_mode == "LIVE") and has_token

            # Instantiate INDstocks API client for this account
            client = INDstocksClient(
                access_token=acc.get("access_token", "").strip(),
                is_paper=not is_live_order
            )

            product = best_opp["product"]
            order_res = client.place_order(
                txn_type="BUY",
                symbol=symbol,
                security_id=best_opp["security_id"],
                qty=qty,
                order_type="MARKET",
                product=product,
                limit_price=best_opp["current_price"],
                exchange="NSE",
                segment=best_opp["segment"]
            )

            if order_res.get("status") == "success":
                new_trade = {
                    "id": f"TRD-{uuid.uuid4().hex[:8].upper()}",
                    "account_id": acc["id"],
                    "account_name": acc["name"],
                    "symbol": symbol,
                    "security_id": best_opp["security_id"],
                    "trade_type": best_opp["trade_type"],
                    "product": product,
                    "qty": qty,
                    "entry_price": best_opp["current_price"],
                    "current_price": best_opp["current_price"],
                    "target_price": best_opp["target_price"],
                    "target_pct": best_opp["target_pct"],
                    "stoploss_price": best_opp["stoploss_price"],
                    "stoploss_pct": best_opp["stoploss_pct"],
                    "score": best_opp["score"],
                    "entry_time": time.time(),
                    "entry_date": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "order_id": order_res.get("order_id", ""),
                    "mode": order_res.get("mode", "PAPER"),
                    "unrealized_pnl": 0.0,
                    "pnl_pct": 0.0
                }
                self.active_trades.append(new_trade)
                self.log(
                    f"AUTO-BUY: {symbol} x {qty} @ ₹{best_opp['current_price']} for {acc['name']} ({best_opp['trade_type']})",
                    "SUCCESS"
                )
        self.save_trades()

    def close_trade(self, trade: Dict, exit_price: float, reason: str):
        qty = trade["qty"]
        pnl = round((exit_price - trade["entry_price"]) * qty, 2)
        pnl_pct = round(((exit_price - trade["entry_price"]) / trade["entry_price"]) * 100.0, 2)

        # Place sell order via INDstocks client
        acc_token = ""
        trade_mode = trade.get("mode", "PAPER")
        if trade_mode == "LIVE":
            accounts = get_active_accounts()
            for a in accounts:
                if a.get("id") == trade.get("account_id"):
                    acc_token = a.get("access_token", "").strip()
                    break
        is_paper = (trade_mode != "LIVE") or (not acc_token)
        client = INDstocksClient(access_token=acc_token, is_paper=is_paper)
        client.place_order(
            txn_type="SELL",
            symbol=trade["symbol"],
            security_id=trade["security_id"],
            qty=qty,
            order_type="MARKET",
            product=trade["product"]
        )

        completed_trade = trade.copy()
        completed_trade["exit_price"] = float(exit_price)
        completed_trade["exit_time"] = time.time()
        completed_trade["exit_date"] = time.strftime("%Y-%m-%d %H:%M:%S")
        if not completed_trade.get("entry_date"):
            completed_trade["entry_date"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(trade.get("entry_time", time.time())))
        dur_sec = max(0, int(completed_trade["exit_time"] - trade.get("entry_time", completed_trade["exit_time"])))
        completed_trade["duration_sec"] = dur_sec
        mins = dur_sec // 60
        secs = dur_sec % 60
        completed_trade["duration_str"] = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
        completed_trade["exit_reason"] = reason
        completed_trade["pnl"] = pnl
        completed_trade["pnl_pct"] = pnl_pct

        self.trade_history.insert(0, completed_trade)
        self.daily_realized_pnl += pnl

        log_level = "SUCCESS" if pnl >= 0 else "WARNING"
        self.log(
            f"AUTO-SELL: {trade['symbol']} exited @ ₹{exit_price} | P&L: ₹{pnl} ({pnl_pct}%) | Reason: {reason}",
            log_level
        )
        self.save_trades()

    def emergency_kill_all(self):
        """Immediately closes all open trades across all accounts and halts trading."""
        self.risk_manager.emergency_halt = True
        self.is_running = False
        trades_to_close = list(self.active_trades)
        for t in trades_to_close:
            curr_price = t.get("current_price", t["entry_price"])
            self.close_trade(t, curr_price, "EMERGENCY_KILL_SWITCH")
        self.active_trades = []
        self.save_trades()
        self.log("EMERGENCY KILL SWITCH ACTIVATED! All open positions squared off immediately.", "DANGER")

    def get_dashboard_summary(self) -> Dict:
        active_pnl = sum(t.get("unrealized_pnl", 0.0) for t in self.active_trades)
        total_pnl = round(self.daily_realized_pnl + active_pnl, 2)

        closed_trades = len(self.trade_history)
        winning_trades = sum(1 for t in self.trade_history if t.get("pnl", 0.0) > 0)
        win_rate = round((winning_trades / closed_trades * 100.0), 1) if closed_trades > 0 else 0.0

        return {
            "is_running": self.is_running,
            "emergency_halt": self.risk_manager.emergency_halt,
            "active_trades_count": len(self.active_trades),
            "closed_trades_count": closed_trades,
            "daily_realized_pnl": round(self.daily_realized_pnl, 2),
            "active_unrealized_pnl": round(active_pnl, 2),
            "total_pnl": total_pnl,
            "win_rate": win_rate
        }
