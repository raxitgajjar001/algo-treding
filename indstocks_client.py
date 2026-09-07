import time
import uuid
import requests
from typing import Dict, Any, Optional

class INDstocksClient:
    BASE_URL = "https://api.indstocks.com"

    def __init__(self, access_token: str = "", is_paper: bool = True):
        self.access_token = access_token.strip() if access_token else ""
        self.is_paper = is_paper or (not self.access_token)
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": self.access_token,
            "Content-Type": "application/json",
            "Accept": "application/json"
        })

    def get_funds(self, fallback_capital: float = 100000.0) -> Dict[str, Any]:
        """Fetch real funds from INDstocks or return paper portfolio funds."""
        if self.is_paper or not self.access_token:
            return {
                "status": "success",
                "available_margin": fallback_capital,
                "used_margin": 0.0,
                "total_funds": fallback_capital,
                "mode": "PAPER"
            }
        try:
            res = self.session.get(f"{self.BASE_URL}/user/funds", timeout=5)
            if res.status_code == 200:
                data = res.json()
                return {"status": "success", "mode": "LIVE", **data}
            return {
                "status": "error",
                "message": f"HTTP {res.status_code}: {res.text}",
                "available_margin": fallback_capital,
                "mode": "FALLBACK"
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
                "available_margin": fallback_capital,
                "mode": "FALLBACK"
            }

    def place_order(
        self,
        txn_type: str,
        symbol: str,
        security_id: str,
        qty: int,
        order_type: str = "MARKET",
        product: str = "INTRADAY",
        limit_price: float = 0.0,
        exchange: str = "NSE",
        segment: str = "EQUITY"
    ) -> Dict[str, Any]:
        """
        Executes order via INDstocks REST API or via realistic Paper Trading simulator.
        product: INTRADAY (MIS) or CNC (Delivery) or MARGIN
        txn_type: BUY or SELL
        """
        txn_type = txn_type.upper()
        if self.is_paper or not self.access_token:
            # Paper execution
            order_id = f"PAPER-{uuid.uuid4().hex[:10].upper()}"
            return {
                "status": "success",
                "mode": "PAPER",
                "order_id": order_id,
                "txn_type": txn_type,
                "symbol": symbol,
                "security_id": security_id,
                "qty": qty,
                "product": product,
                "order_type": order_type,
                "price": limit_price,
                "timestamp": time.time(),
                "message": "Simulated Paper Order Executed Successfully"
            }

        payload = {
            "txn_type": txn_type,
            "exchange": exchange,
            "segment": segment,
            "product": product,
            "order_type": order_type,
            "validity": "DAY",
            "security_id": str(security_id),
            "qty": int(qty)
        }
        if order_type == "LIMIT" and limit_price > 0:
            payload["limit_price"] = float(limit_price)

        try:
            res = self.session.post(f"{self.BASE_URL}/order", json=payload, timeout=8)
            if res.status_code in [200, 201]:
                return {"status": "success", "mode": "LIVE", **res.json()}
            return {
                "status": "error",
                "mode": "LIVE",
                "code": res.status_code,
                "message": f"INDstocks error ({res.status_code}): {res.text}"
            }
        except Exception as e:
            return {
                "status": "error",
                "mode": "LIVE",
                "message": f"Connection exception: {str(e)}"
            }

    def place_smart_order(
        self,
        txn_type: str,
        symbol: str,
        security_id: str,
        qty: int,
        sl_trigger: float,
        tgt_trigger: float
    ) -> Dict[str, Any]:
        """Place GTT / Smart Bracket order on INDstocks."""
        if self.is_paper or not self.access_token:
            return {
                "status": "success",
                "mode": "PAPER",
                "order_id": f"SMART-{uuid.uuid4().hex[:8].upper()}",
                "sl_trigger": sl_trigger,
                "tgt_trigger": tgt_trigger
            }
        payload = {
            "txn_type": txn_type,
            "security_id": str(security_id),
            "qty": int(qty),
            "sl_trigger_price": sl_trigger,
            "tgt_trigger_price": tgt_trigger
        }
        try:
            res = self.session.post(f"{self.BASE_URL}/smart/order", json=payload, timeout=8)
            return res.json() if res.status_code == 200 else {"status": "error", "text": res.text}
        except Exception as e:
            return {"status": "error", "message": str(e)}
