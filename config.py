import os
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

SETTINGS_FILE = DATA_DIR / "settings.json"
ACCOUNTS_FILE = DATA_DIR / "accounts.json"
TRADES_FILE = DATA_DIR / "trades.json"
NEWS_CACHE_FILE = DATA_DIR / "news_cache.json"

DEFAULT_SETTINGS = {
    "engine_active": False,
    "mode": "PAPER",  # "PAPER" or "LIVE"
    "capital_allocation_pct": 25.0,  # Max % of total capital across ALL active trades combined (e.g. 25%)
    "max_daily_loss": 2500.0,
    "max_concurrent_trades": 5,
    "intraday_target_pct": 1.8,
    "intraday_stoploss_pct": 0.9,
    "intraday_squareoff_time": "15:15",
    "min_confidence_score": 85,  # High-accuracy confirmation threshold
    "auto_swing_enabled": False,  # STRICTLY INTRADAY ONLY (No overnight holding)
    "product": "INTRADAY"
}

def get_settings():
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                merged = DEFAULT_SETTINGS.copy()
                merged.update(saved)
                return merged
        except Exception:
            return DEFAULT_SETTINGS.copy()
    return DEFAULT_SETTINGS.copy()

def update_settings(new_settings: dict):
    current = get_settings()
    current.update(new_settings)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2)
    return current
