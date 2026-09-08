"""
Angel One SmartAPI Official Integration Service
Supports:
1. Automated TOTP session generation via pyotp
2. Real-time Market Data & Live Ticks
3. Standardized Lot-size F&O MIS Execution
4. Live Funds & Margin Sync
"""

import os
import json
import time
import pyotp
from typing import Dict, Any, Optional
from SmartApi import SmartConnect

ANGEL_CONFIG_FILE = os.path.join(os.path.dirname(__file__), "data", "angel_config.json")

class AngelOneService:
    def __init__(self):
        self.client = None
        self.auth_data = {}
        self.is_authenticated = False
        self.feed_token = ""
        self.jwt_token = ""
        self.config = self.load_config()
        self.candle_cache = {}
        self.last_candle_req = 0

    def load_config(self) -> Dict[str, Any]:
        if os.path.exists(ANGEL_CONFIG_FILE):
            try:
                with open(ANGEL_CONFIG_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "client_code": "",
            "pin": "",
            "api_key": "",
            "totp_secret": "",
            "is_enabled": False
        }

    def save_config(self, cfg: Dict[str, Any]):
        self.config.update(cfg)
        os.makedirs(os.path.dirname(ANGEL_CONFIG_FILE), exist_ok=True)
        with open(ANGEL_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=2)

    def login(self, client_code: str = "", pin: str = "", api_key: str = "", totp_secret: str = "") -> Dict[str, Any]:
        client_code = client_code or self.config.get("client_code", "")
        pin = pin or self.config.get("pin", "")
        api_key = api_key or self.config.get("api_key", "")
        totp_secret = totp_secret or self.config.get("totp_secret", "")

        if not (client_code and pin and api_key and totp_secret):
            return {
                "status": "error",
                "message": "Client Code, PIN, API Key, અને TOTP Secret ચારેય વિગતો જરૂરી છે."
            }

        try:
            # Generate 6-digit TOTP
            totp = pyotp.TOTP(totp_secret.replace(" ", "").strip()).now()
            
            smart_api = SmartConnect(api_key=api_key.strip())
            data = smart_api.generateSession(client_code.strip(), pin.strip(), totp)
            
            if data and data.get("status") and data.get("data"):
                self.client = smart_api
                self.auth_data = data.get("data")
                self.jwt_token = self.auth_data.get("jwtToken", "")
                self.feed_token = smart_api.getfeedToken()
                self.is_authenticated = True

                self.save_config({
                    "client_code": client_code,
                    "pin": pin,
                    "api_key": api_key,
                    "totp_secret": totp_secret,
                    "is_enabled": True
                })

                return {
                    "status": "success",
                    "message": "Angel One SmartAPI સફળતાપૂર્વક કનેક્ટ થઈ ગયું છે!",
                    "client_name": self.auth_data.get("name", client_code),
                    "client_code": client_code
                }
            else:
                return {
                    "status": "error",
                    "message": data.get("message", "Login નિષ્ફળ રહ્યું. કૃપા કરીને API Key, PIN અથવા TOTP તપાસો.")
                }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Angel One Login એરર: {str(e)}"
            }

    def get_funds(self) -> Dict[str, Any]:
        if not self.is_authenticated or not self.client:
            return {"status": "error", "message": "Angel One કનેક્ટ નથી"}
        try:
            res = self.client.rmsLimit()
            if res and res.get("status"):
                funds_data = res.get("data", {})
                net_avail = float(funds_data.get("net", 0.0))
                return {
                    "status": "success",
                    "available_cash": net_avail,
                    "total_margin": float(funds_data.get("availablecash", net_avail)),
                    "utilized_margin": float(funds_data.get("utiliseddebits", 0.0))
                }
        except Exception as e:
            return {"status": "error", "message": str(e)}
        return {"status": "error", "message": "Funds data unavailable"}

    def get_ltp(self, symbol: str) -> Optional[Dict[str, Any]]:
        if not self.is_authenticated or not self.client:
            return None
        tokens = {
            "NIFTY": ("NSE", "Nifty 50", "99926000"),
            "BANKNIFTY": ("NSE", "Nifty Bank", "99926009"),
            "FINNIFTY": ("NSE", "Nifty Fin Services", "99926037"),
            "MIDCPNIFTY": ("NSE", "NIFTY MID SELECT", "99926074"),
            "SENSEX": ("BSE", "SENSEX", "1")
        }
        info = tokens.get(symbol.upper())
        if not info:
            return None
        ex, sym, tok = info
        try:
            res = self.client.ltpData(ex, sym, tok)
            if res and res.get("status") and res.get("data"):
                d = res["data"]
                ltp = float(d.get("ltp", 0.0))
                close = float(d.get("close", ltp))
                chg = round(((ltp - close) / close) * 100.0, 2) if close > 0 else 0.0
                return {"ltp": ltp, "change_pct": chg, "open": float(d.get("open", 0)), "high": float(d.get("high", 0)), "low": float(d.get("low", 0)), "close": close}
        except Exception:
            pass
        return None

    def get_candles(self, symbol: str, interval: str = "5m") -> Optional[list]:
        if not self.is_authenticated or not self.client:
            return None

        cache_key = f"{symbol.upper()}_{interval}"
        now_ts = time.time()
        cached = self.candle_cache.get(cache_key)
        if cached and (now_ts - cached["time"] < 3.5):
            return cached["data"]

        tokens = {
            "NIFTY": ("NSE", "99926000"),
            "BANKNIFTY": ("NSE", "99926009"),
            "FINNIFTY": ("NSE", "99926037"),
            "MIDCPNIFTY": ("NSE", "99926074"),
        }
        info = tokens.get(symbol.upper())
        if not info:
            return None
        ex, tok = info

        intv_map = {
            "1m": "ONE_MINUTE",
            "5m": "FIVE_MINUTE",
            "15m": "FIFTEEN_MINUTE",
            "30m": "THIRTY_MINUTE",
            "1h": "ONE_HOUR",
            "1d": "ONE_DAY"
        }
        angel_intv = intv_map.get(interval, "FIVE_MINUTE")

        from datetime import datetime
        import dateutil.parser
        now = datetime.now()
        from_str = now.strftime("%Y-%m-%d 09:15")
        to_str = now.strftime("%Y-%m-%d %H:%M")

        params = {
            "exchange": ex,
            "symboltoken": tok,
            "interval": angel_intv,
            "fromdate": from_str,
            "todate": to_str
        }

        # Rate limiter: minimum 1.2s between calls
        if (now_ts - self.last_candle_req) < 1.2:
            time.sleep(1.2 - (now_ts - self.last_candle_req))

        try:
            self.last_candle_req = time.time()
            hist = self.client.getCandleData(params)
            raw = hist.get("data", [])
            candles = []
            for item in raw:
                # item: [iso_date, open, high, low, close, volume]
                iso_time, o, h, l, c, v = item
                dt = dateutil.parser.parse(iso_time)
                epoch = int(dt.timestamp()) + 19800
                candles.append({
                    "time": epoch,
                    "open": round(float(o), 2),
                    "high": round(float(h), 2),
                    "low": round(float(l), 2),
                    "close": round(float(c), 2),
                    "volume": int(v)
                })
            if candles:
                self.candle_cache[cache_key] = {"time": time.time(), "data": candles}
                return candles
        except Exception:
            pass

        if cached:
            return cached["data"]
        return None

    def place_order(self, tradingsymbol: str, symboltoken: str, exchange: str, transaction_type: str, quantity: int, order_type: str = "MARKET", price: float = 0.0) -> Dict[str, Any]:
        if not self.is_authenticated or not self.client:
            return {"status": "error", "message": "Angel One is not authenticated"}
        try:
            params = {
                "variety": "NORMAL",
                "tradingsymbol": tradingsymbol,
                "symboltoken": str(symboltoken),
                "transactiontype": transaction_type.upper(),
                "exchange": exchange.upper(),
                "ordertype": order_type.upper(),
                "producttype": "INTRADAY",
                "duration": "DAY",
                "price": str(price) if order_type == "LIMIT" else "0",
                "quantity": str(quantity)
            }
            order_res = self.client.placeOrder(params)
            return {"status": "success", "order_id": order_res}
        except Exception as e:
            return {"status": "error", "message": str(e)}

angel_one_service = AngelOneService()
# Auto-authenticate if config exists
if angel_one_service.config.get("client_code") and angel_one_service.config.get("api_key"):
    try:
        angel_one_service.login()
    except Exception:
        pass
