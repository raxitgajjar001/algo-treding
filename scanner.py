import time
import random
from typing import List, Dict
from news_analyzer import get_ticker_news_boost
from config import get_settings

WATCHLIST = [
    {"symbol": "RELIANCE", "name": "Reliance Industries Ltd", "security_id": "2885", "base_price": 1309.50, "segment": "EQUITY"},
    {"symbol": "HDFCBANK", "name": "HDFC Bank Ltd", "security_id": "1333", "base_price": 710.50, "segment": "EQUITY"},
    {"symbol": "ICICIBANK", "name": "ICICI Bank Ltd", "security_id": "4963", "base_price": 1427.50, "segment": "EQUITY"},
    {"symbol": "SBIN", "name": "State Bank of India", "security_id": "3045", "base_price": 1005.90, "segment": "EQUITY"},
    {"symbol": "TATAMOTORS", "name": "Tata Motors Ltd", "security_id": "3456", "base_price": 307.25, "segment": "EQUITY"},
    {"symbol": "TCS", "name": "Tata Consultancy Services", "security_id": "11536", "base_price": 2270.00, "segment": "EQUITY"},
    {"symbol": "INFY", "name": "Infosys Ltd", "security_id": "1594", "base_price": 1087.50, "segment": "EQUITY"},
    {"symbol": "BHARTIARTL", "name": "Bharti Airtel Ltd", "security_id": "10604", "base_price": 1854.00, "segment": "EQUITY"},
    {"symbol": "LT", "name": "Larsen & Toubro Ltd", "security_id": "11483", "base_price": 3999.00, "segment": "EQUITY"},
    {"symbol": "BAJFINANCE", "name": "Bajaj Finance Ltd", "security_id": "317", "base_price": 1060.00, "segment": "EQUITY"},
    {"symbol": "MARUTI", "name": "Maruti Suzuki India", "security_id": "10999", "base_price": 12760.00, "segment": "EQUITY"},
    {"symbol": "ITC", "name": "ITC Ltd", "security_id": "1660", "base_price": 263.50, "segment": "EQUITY"},
    {"symbol": "NIFTY", "name": "Nifty 50 Index", "security_id": "26000", "base_price": 23779.15, "segment": "DERIVATIVE"},
    {"symbol": "BANKNIFTY", "name": "Bank Nifty Index", "security_id": "26001", "base_price": 57088.30, "segment": "DERIVATIVE"}
]

class MarketScanner:
    def __init__(self):
        self.last_scan_time = 0
        self.cached_opportunities = []

    def get_live_price(self, item: Dict) -> float:
        from config import DATA_DIR
        import json
        real_file = DATA_DIR / "real_prices.json"
        if real_file.exists():
            try:
                with open(real_file, "r", encoding="utf-8") as f:
                    rp = json.load(f)
                    sym = item["symbol"]
                    if sym in rp and rp[sym].get("price", 0) > 0:
                        return float(rp[sym]["price"])
            except Exception:
                pass
        return float(item["base_price"])

    def scan_opportunities(self) -> List[Dict]:
        settings = get_settings()
        min_score = settings.get("min_confidence_score", 80)
        intraday_target_pct = settings.get("intraday_target_pct", 2.0)
        intraday_sl_pct = settings.get("intraday_stoploss_pct", 1.0)
        swing_target_pct = settings.get("swing_target_pct", 6.0)
        swing_sl_pct = settings.get("swing_stoploss_pct", 2.5)

        results = []

        for item in WATCHLIST:
            symbol = item["symbol"]
            current_price = self.get_live_price(item)

            # Simulated Technical Confluence factors
            # 1. EMA 9 vs EMA 21 Trend alignment
            ema_trend = random.choice(["BULLISH", "BULLISH", "NEUTRAL", "BEARISH"])
            # 2. RSI (14) Momentum
            rsi = round(random.uniform(45.0, 78.0), 1)
            # 3. Volume Surge
            vol_multiplier = round(random.uniform(1.0, 2.8), 2)

            # Base score calculation
            score = 50.0
            if ema_trend == "BULLISH":
                score += 18.0
            if 55.0 <= rsi <= 72.0:
                score += 15.0
            if vol_multiplier > 1.6:
                score += 15.0

            # 4. News Boost from Live News Engine
            news_boost = get_ticker_news_boost(symbol)
            score += news_boost

            score = min(98.0, max(30.0, round(score, 1)))

            # Categorize trade type
            # If news boost is high and volume surge is immense (>2.0x), candidate for Short-Swing (2-7 days)
            is_swing_candidate = (news_boost >= 8.0 or vol_multiplier >= 2.1) and score >= 85.0
            trade_type = "SWING_DELIVERY" if is_swing_candidate else "INTRADAY"

            if trade_type == "SWING_DELIVERY":
                target_pct = swing_target_pct
                sl_pct = swing_sl_pct
                max_hold = "2 - 7 Days (Auto-Exit at 7d)"
                product = "CNC"
            else:
                target_pct = intraday_target_pct
                sl_pct = intraday_sl_pct
                max_hold = "Intraday (Auto-Exit 15:15 IST)"
                product = "INTRADAY"

            target_price = round(current_price * (1.0 + target_pct / 100.0), 2)
            sl_price = round(current_price * (1.0 - sl_pct / 100.0), 2)
            risk_reward = round(target_pct / sl_pct, 2)

            status = "SIGNAL_READY" if score >= min_score else "MONITORING"

            results.append({
                "symbol": symbol,
                "name": item["name"],
                "security_id": item["security_id"],
                "segment": item["segment"],
                "product": product,
                "current_price": current_price,
                "score": score,
                "trade_type": trade_type,
                "status": status,
                "target_price": target_price,
                "target_pct": target_pct,
                "stoploss_price": sl_price,
                "stoploss_pct": sl_pct,
                "risk_reward": f"1:{risk_reward}",
                "max_hold": max_hold,
                "rsi": rsi,
                "volume_surge": f"{vol_multiplier}x",
                "news_boost": f"+{news_boost}" if news_boost > 0 else f"{news_boost}",
                "timestamp": time.time()
            })

        # Sort descending by score
        results.sort(key=lambda x: x["score"], reverse=True)
        self.cached_opportunities = results
        self.last_scan_time = time.time()
        return results
