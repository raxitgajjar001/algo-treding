import json
import uuid
from typing import List, Dict, Optional
from config import ACCOUNTS_FILE

DEFAULT_ACCOUNTS = [
    {
        "id": "acc-primary-1",
        "name": "Primary INDstocks Account",
        "broker": "INDstocks",
        "access_token": "",
        "total_capital": 100000.0,
        "capital_allocation_pct": 10.0,
        "max_loss_limit": 2500.0,
        "is_active": True,
        "is_paper": True,
        "created_at": "2026-09-07T10:00:00"
    }
]

def load_accounts() -> List[Dict]:
    if ACCOUNTS_FILE.exists():
        try:
            with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception:
            pass
    save_accounts(DEFAULT_ACCOUNTS)
    return [acc.copy() for acc in DEFAULT_ACCOUNTS]

def save_accounts(accounts: List[Dict]):
    with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
        json.dump(accounts, f, indent=2)

def get_active_accounts() -> List[Dict]:
    return [acc for acc in load_accounts() if acc.get("is_active", True)]

def add_account(account_data: Dict) -> Dict:
    accounts = load_accounts()
    new_acc = {
        "id": f"acc-{uuid.uuid4().hex[:8]}",
        "name": account_data.get("name", "New Account"),
        "broker": account_data.get("broker", "INDstocks"),
        "access_token": account_data.get("access_token", ""),
        "total_capital": float(account_data.get("total_capital", 50000.0)),
        "capital_allocation_pct": float(account_data.get("capital_allocation_pct", 10.0)),
        "max_loss_limit": float(account_data.get("max_loss_limit", 2000.0)),
        "is_active": account_data.get("is_active", True),
        "is_paper": account_data.get("is_paper", True)
    }
    accounts.append(new_acc)
    save_accounts(accounts)
    return new_acc

def update_account(acc_id: str, updates: Dict) -> Optional[Dict]:
    accounts = load_accounts()
    updated_account = None
    for acc in accounts:
        if acc["id"] == acc_id:
            for k, v in updates.items():
                if k != "id":
                    acc[k] = v
            updated_account = acc
            break
    if updated_account:
        save_accounts(accounts)
    return updated_account

def delete_account(acc_id: str) -> bool:
    accounts = load_accounts()
    new_accounts = [acc for acc in accounts if acc["id"] != acc_id]
    if len(new_accounts) < len(accounts):
        save_accounts(new_accounts)
        return True
    return False

def calculate_quantity_for_account(account: Dict, current_price: float) -> int:
    """Calculates trade size strictly according to the account's capital allocation percentage."""
    if current_price <= 0:
        return 0
    total_capital = float(account.get("total_capital", 10000.0))
    allocation_pct = float(account.get("capital_allocation_pct", 10.0))
    allocated_rupees = total_capital * (allocation_pct / 100.0)
    qty = int(allocated_rupees // current_price)
    return max(1, qty) if allocated_rupees >= current_price else 0
