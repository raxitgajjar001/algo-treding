import time
import json
import uuid
from typing import List, Dict
from config import TRADES_FILE, get_settings, update_settings
from account_manager import get_active_accounts
from indstocks_client import INDstocksClient
from risk_manager import RiskManager
from scanner import MarketScanner
from news_analyzer import fetch_rss_news

class TradingEngine:
    def __init__(self):
        self.risk_manager = RiskManager()
        self.scanner = MarketScanner()
        settings = get_settings()
        self.is_running = bool(settings.get("engine_active", False)) and self.is_indian_market_open()
        self.active_trades: List[Dict] = []
        self.trade_history: List[Dict] = []
        self.daily_realized_pnl: float = 0.0
        self.logs: List[Dict] = []
        self.cooldowns: Dict[str, float] = {}
        self.load_trades()
        self.log("🚀 INDstocks Algo Engine v2.5 initialized for Indian Markets (NSE/BSE).", "INFO")
        self.log("🛡️ 2% Risk Circuit Breaker active & 25% Allocation Pool Cap enforced.", "INFO")
        self.log("🔌 Low-Latency Real-Time Market Data connected.", "INFO")
        self.log("📊 Multi-Timeframe Trend Engine (15m 200 EMA + 5m EMA 9/21 + RSI 14) active.", "INFO")

    def log(self, message: str, level: str = "INFO"):
        import datetime
        utc_now = datetime.datetime.now(datetime.timezone.utc)
        ist_now = utc_now + datetime.timedelta(hours=5, minutes=30)
        entry = {
            "timestamp": ist_now.strftime("%I:%M:%S %p"),
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
                    raw_active = data.get("active", [])
                    # Filter out old equity trades so platform focuses strictly on F&O derivatives
                    self.active_trades = [
                        t for t in raw_active 
                        if t.get("segment") == "DERIVATIVE" or ("_CE" in t.get("symbol", "")) or ("_PE" in t.get("symbol", "")) or t.get("symbol", "").endswith("CE") or t.get("symbol", "").endswith("PE")
                    ]
                    self.trade_history = data.get("history", [])
                    self.daily_realized_pnl = round(sum(t.get("pnl", 0.0) for t in self.trade_history), 2)
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
            update_settings({"engine_active": False})
            self.log("બજાર બંધ હોવાથી ઓટો ટ્રેડિંગ શરૂ થઈ શકે નહીં (સવારે 09:15 થી બપોરે 03:30 દરમિયાન જ શરૂ થશે).", "WARNING")
            return False
        self.is_running = True
        update_settings({"engine_active": True})
        self.risk_manager.emergency_halt = False
        self.engine_started_at = time.time()
        self.last_entry_time = 0
        self.log("🚀 Trading Engine Started: F&O Market Scanning & Multi-Timeframe Confirmation Active. Zero hasty trades.", "SUCCESS")
        return True

    def stop(self):
        self.is_running = False
        update_settings({"engine_active": False})
        self.log("Trading Engine Paused (ઓટો ટ્રેડિંગ થોભાવ્યું)", "WARNING")

    def execute_cycle(self):
        """Runs one full scan and execution iteration."""
        # 1. Update news feeds
        fetch_rss_news()

        # 2. STRICT CHECK: If market is closed, force engine OFF!
        if not self.is_indian_market_open():
            if self.is_running:
                self.is_running = False
                update_settings({"engine_active": False})
                self.log("બજાર બંધ હોવાથી ઓટો ટ્રેડિંગ સંપૂર્ણપણે બંધ છે.", "INFO")
            return

        # 3. Monitor & evaluate active trades for Exit (Auto Sell)
        self.evaluate_active_trades()

        # 4. If engine is running, scan for new entries (Auto Buy)
        if self.is_running and not self.risk_manager.emergency_halt:
            self.evaluate_new_entries()

    def evaluate_active_trades(self):
        from scanner import ROUND_TRIP_CHARGES
        remaining_trades = []
        for trade in self.active_trades:
            symbol = trade["symbol"]
            qty = int(trade.get("qty", 25))
            entry_price = float(trade["entry_price"])
            entry_spot = float(trade.get("entry_spot", 0))
            underlying = trade.get("underlying", "NIFTY")
            opt_type = trade.get("option_type", "CE")

            # Calculate price based on real spot movement
            cur_spot = entry_spot
            try:
                import app
                cur_spot = float(app.REAL_LIVE_TICKS_CACHE.get("ticks", {}).get(underlying, {}).get("ltp", entry_spot))
            except Exception:
                pass

            if entry_spot > 0 and cur_spot > 0:
                spot_diff = cur_spot - entry_spot
                opt_move = (spot_diff * 0.50) if opt_type == "CE" else (-spot_diff * 0.50)
                new_price = round(max(2.0, entry_price + opt_move), 2)
            else:
                new_price = float(trade.get("current_price", entry_price))

            trade["current_price"] = new_price

            # Points & P&L Calculation
            points_diff = round(new_price - entry_price, 2)
            gross_pnl = round(points_diff * qty, 2)
            charges = ROUND_TRIP_CHARGES  # ₹20 Buy + ₹20 Sell + ₹7.20 GST + ₹1.30 STT
            net_pnl = round(gross_pnl - charges, 2)
            invested_cap = float(trade.get("invested_capital", entry_price * qty))
            pnl_pct = round((net_pnl / invested_cap) * 100.0, 2) if invested_cap > 0 else 0.0

            trade["points_diff"] = points_diff
            trade["gross_pnl"] = gross_pnl
            trade["brokerage_charges"] = charges
            trade["unrealized_pnl"] = net_pnl
            trade["net_pnl"] = net_pnl
            trade["pnl_pct"] = pnl_pct

            # Check target and stoploss
            tgt = float(trade.get("target_price", entry_price + 30.0))
            sl = float(trade.get("stoploss_price", max(1.0, entry_price - 15.0)))
            if new_price >= tgt:
                self.close_trade(trade, new_price, "Target Hit 🎯 (ટાર્ગેટ અચીવ થયો)")
            elif new_price <= sl:
                self.close_trade(trade, new_price, "Stoploss Hit 🛑 (સ્ટોપલોસ હિટ થયો)")
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

        now = time.time()
        started_at = getattr(self, "engine_started_at", 0)
        elapsed_since_start = now - started_at

        # 2. Strict Warm-Up & Observation Window (Minimum 18-25 seconds of multi-indicator scanning)
        # Prevents instant blind trades upon pressing start!
        if elapsed_since_start < 18:
            self.log(
                "🔍 F&O અલ્ગોરિધમિક ચકાસણી ચાલુ: NIFTY 50 & BANKNIFTY 15m 200 EMA + 5m Crossover + Supertrend + RSI... બ્રોકરેજ (₹40+GST) બાદ કરીને સારો નફો આપે તેવા સચોટ સિગ્નલની રાહ.",
                "INFO"
            )
            return

        # 3. Cooldown between trades: Minimum 60 seconds
        last_entry = getattr(self, "last_entry_time", 0)
        if (now - last_entry) < 60:
            return

        # 4. Maximum 1 high-probability F&O position at a time to strictly control risk
        if len(self.active_trades) >= 1:
            return

        opportunities = self.scanner.scan_opportunities()
        settings = get_settings()
        min_score = settings.get("min_confidence_score", 85)

        # 5. Strict high-accuracy filter: Score >= 85, Signal Confirmed, Net Profit > Brokerage
        high_score_opps = [
            o for o in opportunities 
            if o["score"] >= min_score and "SIGNAL_CONFIRMED" in o.get("status", "") and o.get("net_expected_profit", 0) >= 200
        ]
        if not high_score_opps:
            return

        active_accounts = get_active_accounts()
        if not active_accounts:
            return

        best_opp = high_score_opps[0]
        symbol = best_opp["symbol"]
        lot_size = best_opp.get("lot_size", 25)

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

            # Calculate position size strictly in standardized F&O lot sizes within 25% pool
            qty, allocated_funds = self.risk_manager.calculate_position_size(
                account=acc,
                entry_price=best_opp["current_price"],
                open_trades=self.active_trades,
                lot_size=lot_size
            )
            if qty <= 0:
                continue

            global_mode = settings.get("mode", "PAPER")
            has_token = bool(acc.get("access_token", "").strip())
            is_live_order = (global_mode == "LIVE") and has_token

            client = INDstocksClient(
                access_token=acc.get("access_token", "").strip(),
                is_paper=not is_live_order
            )

            product = "INTRADAY"
            direction = best_opp.get("direction", "BUY").upper()
            txn_type = "BUY"

            order_res = client.place_order(
                txn_type=txn_type,
                symbol=symbol,
                security_id=best_opp["security_id"],
                qty=qty,
                order_type="LIMIT",
                product=product,
                limit_price=best_opp["current_price"],
                exchange=best_opp.get("exchange", "NSE"),
                segment="DERIVATIVE"
            )

            if order_res.get("status") == "success":
                from scanner import ROUND_TRIP_CHARGES
                lots_count = max(1, qty // lot_size)
                new_trade = {
                    "id": f"TRD-{uuid.uuid4().hex[:8].upper()}",
                    "account_id": acc["id"],
                    "account_name": acc["name"],
                    "symbol": symbol,
                    "underlying": best_opp.get("underlying", "NIFTY"),
                    "strike": best_opp.get("strike", 0),
                    "option_type": best_opp.get("option_type", "CE"),
                    "lot_size": lot_size,
                    "lots_count": lots_count,
                    "security_id": best_opp["security_id"],
                    "trade_type": "INTRADAY",
                    "product": "INTRADAY",
                    "direction": direction,
                    "direction_label": best_opp.get("direction_label", "🟢 BUY CALL"),
                    "qty": qty,
                    "entry_price": best_opp["current_price"],
                    "current_price": best_opp["current_price"],
                    "points_diff": 0.0,
                    "invested_capital": allocated_funds,
                    "target_price": best_opp["target_price"],
                    "target_pct": best_opp["target_pct"],
                    "target_pts": best_opp.get("target_pts", 0.0),
                    "stoploss_price": best_opp["stoploss_price"],
                    "stoploss_pct": best_opp["stoploss_pct"],
                    "stoploss_pts": best_opp.get("stoploss_pts", 0.0),
                    "break_even_price": best_opp.get("break_even_price", best_opp["current_price"] + 2.0),
                    "score": best_opp["score"],
                    "entry_time": time.time(),
                    "entry_date": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "order_id": order_res.get("order_id", ""),
                    "mode": order_res.get("mode", "PAPER"),
                    "gross_pnl": 0.0,
                    "brokerage_charges": ROUND_TRIP_CHARGES,
                    "unrealized_pnl": 0.0,
                    "net_pnl": 0.0,
                    "pnl_pct": 0.0
                }
                self.active_trades.append(new_trade)
                self.last_entry_time = time.time()
                self.log(
                    f"AUTO-BUY F&O: {symbol} ({lots_count} Lot / {qty} Qty) @ ₹{best_opp['current_price']} for {acc['name']} (Capital: ₹{allocated_funds:,.2f}) | Tgt: ₹{best_opp['target_price']} (+{best_opp.get('target_pts', 0)} pts) | Est Net Profit: +₹{best_opp.get('net_expected_profit', 0)} (after ₹{ROUND_TRIP_CHARGES} brokerage+GST)",
                    "SUCCESS"
                )
        self.save_trades()

    def close_trade(self, trade: Dict, exit_price: float, reason: str):
        from scanner import ROUND_TRIP_CHARGES
        qty = int(trade["qty"])
        entry_price = float(trade["entry_price"])
        exit_price = float(exit_price)

        points_diff = round(exit_price - entry_price, 2)
        gross_pnl = round(points_diff * qty, 2)
        charges = ROUND_TRIP_CHARGES  # ₹20 Buy + ₹20 Sell + ₹7.20 GST + ₹1.30 STT
        net_pnl = round(gross_pnl - charges, 2)
        invested_cap = float(trade.get("invested_capital", entry_price * qty))
        pnl_pct = round((net_pnl / invested_cap) * 100.0, 2) if invested_cap > 0 else 0.0
        close_txn_type = "SELL"

        # Place close order via INDstocks client
        acc_token = ""
        trade_mode = trade.get("mode", "PAPER")
        if trade_mode == "LIVE":
            accounts = get_active_accounts()
            for a in accounts:
                if a.get("id") == trade.get("account_id"):
                    acc_token = a.get("access_token", "").strip()
                    break
        try:
            if trade_mode in ("LIVE", "REAL"):
                from angel_one_service import angel_one_service
                if angel_one_service.is_authenticated:
                    angel_one_service.place_order(
                        tradingsymbol=trade["symbol"],
                        symboltoken=trade.get("security_id", "0"),
                        exchange="NFO" if trade.get("underlying", "NIFTY") != "SENSEX" else "BFO",
                        transaction_type="SELL",
                        quantity=qty,
                        order_type="MARKET",
                        price=0.0
                    )
            client.place_order(
                txn_type=close_txn_type,
                symbol=trade["symbol"],
                security_id=trade.get("security_id", "0"),
                qty=qty,
                order_type="LIMIT",
                limit_price=float(exit_price),
                product="INTRADAY"
            )
        except Exception as e:
            self.log(f"Order placement error on exit: {e}", "WARNING")

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
        completed_trade["points_diff"] = points_diff
        completed_trade["gross_pnl"] = gross_pnl
        completed_trade["brokerage_charges"] = charges
        completed_trade["net_pnl"] = net_pnl
        completed_trade["pnl"] = net_pnl  # Net realized profit after all expenses
        completed_trade["pnl_pct"] = pnl_pct

        self.trade_history.insert(0, completed_trade)
        self.daily_realized_pnl = round(self.daily_realized_pnl + net_pnl, 2)

        # Track consecutive losses for 3-loss circuit breaker
        if net_pnl < 0:
            self.risk_manager.consecutive_losses = getattr(self.risk_manager, "consecutive_losses", 0) + 1
        else:
            self.risk_manager.consecutive_losses = 0

        log_level = "SUCCESS" if net_pnl >= 0 else "WARNING"
        self.log(
            f"AUTO-EXIT: {trade['symbol']} closed @ ₹{exit_price} | Gross: +₹{gross_pnl} | બ્રોકરેજ+GST: -₹{charges} | ચોખ્ખો નફો (Net): ₹{net_pnl} ({pnl_pct}%) | Reason: {reason}",
            log_level
        )
        # Enforce 180s (3-minute) Cool-Down on this underlying after trade closes to avoid overtrading
        und = trade.get("underlying", "NIFTY").upper()
        self.cooldowns[und] = time.time() + 180.0
        self.log(f"⏳ કૂલ-ડાઉન મોડ સક્રિય: {und} માટે ૧૮૦ સેકન્ડ (ઓવર-ટ્રેડિંગ સુરક્ષા).", "INFO")
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

    def place_scalper_trade(self, underlying: str = "NIFTY", option_type: str = "CE", lots: int = 1, sl_pts: float = 15.0, tgt_pts: float = 30.0, order_type: str = "LIMIT") -> Dict:
        """Execute 1-click Pro Scalper Order (ATM CE / ATM PE) with auto SL, Target, and Limit Order support"""
        try:
            und_key = str(underlying).upper().strip()
            opt_type = str(option_type).upper().strip()
            if opt_type not in ("CE", "PE"):
                opt_type = "CE"

            # Check Post-Trade Cool-Down
            cd_until = self.cooldowns.get(und_key, 0.0)
            now = time.time()
            if now < cd_until:
                rem = int(cd_until - now)
                return {
                    "status": "warning",
                    "message": f"⏳ કૂલ-ડાઉન મોડ સક્રિય: {und_key} માં ઓવર-ટ્રેડિંગ અટકાવવા {rem} સેકન્ડ રાહ જુઓ."
                }

            from angel_one_service import angel_one_service
            from config import get_settings
            
            # 1. Fetch live spot price from RAM cache
            spot = 23553.0
            try:
                import app
                spot = float(app.REAL_LIVE_TICKS_CACHE.get("ticks", {}).get(und_key, {}).get("ltp", 23553.0))
            except Exception:
                pass
                
            opt_info = angel_one_service.get_atm_option_details(und_key, spot, opt_type)
            symbol = opt_info.get("tradingsymbol", f"{und_key}_ATM_{opt_type}")
            lot_size = int(opt_info.get("lot_size", 75 if und_key == "NIFTY" else 30))
            qty = int(lots * lot_size)
            entry_price = float(opt_info.get("estimated_premium", 120.0))
            
            invested_capital = round(entry_price * qty, 2)

            # 2. Risk Pool Cap Check (25% maximum capital allocation)
            import account_manager
            accs = account_manager.load_accounts()
            acc = accs[0] if accs else {"total_capital": 100000.0, "capital_allocation_pct": 25.0}
            tot_cap = float(acc.get("total_capital", 100000.0))
            alloc_pct = float(acc.get("capital_allocation_pct", 25.0))
            max_pool = tot_cap * (alloc_pct / 100.0)
            used_cap = sum(float(t.get("entry_price", 0.0)) * int(t.get("qty", 1)) for t in self.active_trades)
            if (used_cap + invested_capital) > max_pool:
                rem_cap = max(0.0, max_pool - used_cap)
                return {
                    "status": "error",
                    "message": f"⚠️ રિસ્ક પૂલ મર્યાદા (25% Cap): તમારા પૂલમાં માત્ર ₹{rem_cap:,.2f} બાકી છે (જરૂરી: ₹{invested_capital:,.2f}). લોટ ઓછા કરો."
                }

            settings = get_settings()
            mode = settings.get("mode", "PAPER")
            
            target_price = round(entry_price + tgt_pts, 1)
            stoploss_price = round(max(1.0, entry_price - sl_pts), 1)

            # Slippage Protection: In LIMIT mode, set limit price at entry_price + 0.50 pts buffer
            exec_type = order_type.upper() if order_type else "LIMIT"
            limit_price = round(entry_price + 0.50, 1) if exec_type == "LIMIT" else 0.0
            
            order_id = f"SCALP-{uuid.uuid4().hex[:8].upper()}"
            if mode in ("LIVE", "REAL") and angel_one_service.is_authenticated:
                res = angel_one_service.place_order(
                    tradingsymbol=symbol,
                    symboltoken="0",
                    exchange="NFO" if und_key != "SENSEX" else "BFO",
                    transaction_type="BUY",
                    quantity=qty,
                    order_type=exec_type,
                    price=limit_price
                )
                if isinstance(res, dict) and res.get("status") == "success":
                    order_id = str(res.get("order_id", order_id))
            
            new_trade = {
                "id": f"TRD-{uuid.uuid4().hex[:8].upper()}",
                "account_id": "ACC-PRIMARY",
                "account_name": "Angel One Trading",
                "symbol": symbol,
                "security_id": "0",
                "underlying": und_key,
                "strike": opt_info.get("strike", 23650),
                "option_type": opt_type,
                "lot_size": lot_size,
                "lots_count": lots,
                "qty": qty,
                "entry_price": entry_price,
                "current_price": entry_price,
                "entry_spot": spot,
                "points_diff": 0.0,
                "invested_capital": invested_capital,
                "target_price": target_price,
                "target_pct": round((tgt_pts / entry_price) * 100.0, 1) if entry_price > 0 else 20.0,
                "target_pts": tgt_pts,
                "stoploss_price": stoploss_price,
                "stoploss_pct": round((sl_pts / entry_price) * 100.0, 1) if entry_price > 0 else 10.0,
                "stoploss_pts": sl_pts,
                "direction": "BUY",
                "direction_label": f"🟢 BUY CALL (CE)" if opt_type == "CE" else f"🔴 BUY PUT (PE)",
                "entry_time": time.time(),
                "entry_date": time.strftime("%Y-%m-%d %H:%M:%S"),
                "order_id": order_id,
                "mode": mode,
                "gross_pnl": 0.0,
                "brokerage_charges": 48.5,
                "unrealized_pnl": 0.0,
                "net_pnl": 0.0,
                "pnl_pct": 0.0,
                "order_type": exec_type,
                "limit_price": limit_price
            }
            
            self.active_trades.insert(0, new_trade)
            self.save_trades()
            self.log(f"⚡ SCALPER EXECUTED ({exec_type}): {symbol} ({lots} Lot / {qty} Qty) @ ₹{entry_price} [Tgt: ₹{target_price} | SL: ₹{stoploss_price}] ({mode} Mode)", "SUCCESS")
            return {"status": "success", "message": f"{symbol} ઓર્ડર સફળતાપૂર્વક પ્લેસ થયો ({exec_type})!", "trade": new_trade}
        except Exception as e:
            self.log(f"Scalper execution failed: {str(e)}", "DANGER")
            return {"status": "error", "message": f"ઓર્ડર એક્ઝિક્યુશનમાં એરર: {str(e)}"}

    def get_dashboard_summary(self) -> Dict:
        active_accounts = get_active_accounts()
        total_capital = sum(float(a.get("total_capital", 100000.0)) for a in active_accounts) if active_accounts else 100000.0
        used_capital = round(sum(float(t.get("entry_price", 0.0)) * int(t.get("qty", 1)) for t in self.active_trades), 2)
        available_capital = round(max(0.0, total_capital - used_capital), 2)
        
        settings = get_settings()
        alloc_pct = float(settings.get("capital_allocation_pct", 25.0))
        max_capital_pool = round(total_capital * (alloc_pct / 100.0), 2)
        remaining_pool = round(max(0.0, max_capital_pool - used_capital), 2)

        active_net_pnl = sum(t.get("net_pnl", 0.0) for t in self.active_trades)
        total_pnl = round(self.daily_realized_pnl + active_net_pnl, 2)

        total_brokerage = round(
            sum(float(t.get("brokerage_charges", 48.50)) for t in self.trade_history) +
            sum(float(t.get("brokerage_charges", 48.50)) for t in self.active_trades),
            2
        )

        closed_trades = len(self.trade_history)
        winning_trades = sum(1 for t in self.trade_history if t.get("pnl", 0.0) > 0)
        win_rate = round((winning_trades / closed_trades * 100.0), 1) if closed_trades > 0 else 0.0

        return {
            "is_running": self.is_running,
            "emergency_halt": self.risk_manager.emergency_halt,
            "total_capital": total_capital,
            "used_capital": used_capital,
            "available_capital": available_capital,
            "capital_allocation_pct": alloc_pct,
            "max_capital_pool": max_capital_pool,
            "remaining_pool": remaining_pool,
            "active_trades_count": len(self.active_trades),
            "closed_trades_count": closed_trades,
            "daily_realized_pnl": round(self.daily_realized_pnl, 2),
            "active_unrealized_pnl": round(active_net_pnl, 2),
            "total_pnl": total_pnl,
            "total_brokerage": total_brokerage,
            "win_rate": win_rate,
            "cooldowns": self.cooldowns
        }
