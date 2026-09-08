import os
import json
import threading
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

SETTINGS_FILE = DATA_DIR / "settings.json"
ACCOUNTS_FILE = DATA_DIR / "accounts.json"
TRADES_FILE = DATA_DIR / "trades.json"
NEWS_CACHE_FILE = DATA_DIR / "news_cache.json"

SETTINGS_LOCK = threading.Lock()

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
    with SETTINGS_LOCK:
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
    with SETTINGS_LOCK:
        try:
            current = DEFAULT_SETTINGS.copy()
            if SETTINGS_FILE.exists():
                try:
                    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                        saved = json.load(f)
                        current.update(saved)
                except Exception:
                    pass
            current.update(new_settings)
            
            # Atomic write to avoid file contention or WinError 32 on Windows
            tmp_file = SETTINGS_FILE.with_suffix(".tmp")
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(current, f, indent=2)
            os.replace(tmp_file, SETTINGS_FILE)
            return current
        except Exception as e:
            print(f"[Settings] Error saving settings: {e}")
            return DEFAULT_SETTINGS.copy()

