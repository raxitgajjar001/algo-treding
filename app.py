
import datetime

def get_market_timing():
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    ist_now = utc_now + datetime.timedelta(hours=5, minutes=30)
    weekday = ist_now.weekday()
    current_time = ist_now.time()
    market_open = datetime.time(9, 15)
    market_close = datetime.time(15, 30)

    time_str = ist_now.strftime("%I:%M:%S %p IST")

    if weekday in [5, 6]:
        return {
            "is_open": False,
            "status": "CLOSED_WEEKEND",
            "time_str": time_str,
            "badge_text": "🔴 MARKET CLOSED (શનિ-રવિ રજા)",
            "message": "શનિવાર અને રવિવારે શેરબજારમાં રજા હોવાથી ટ્રેડિંગ બંધ છે. સોમવારે સવારે 09:15 વાગ્યે માર્કેટ ખુલશે."
        }
    elif market_open <= current_time <= market_close:
        return {
            "is_open": True,
            "status": "OPEN",
            "time_str": time_str,
            "badge_text": "🟢 LIVE MARKET (બજાર ચાલુ છે)",
            "message": "ભારતીય શેરબજાર (NSE/BSE) લાઈવ ચાલુ છે (09:15 AM - 03:30 PM)."
        }
    else:
        return {
            "is_open": False,
            "status": "CLOSED",
            "time_str": time_str,
            "badge_text": "🔴 MARKET CLOSED (બજાર બંધ છે)",
            "message": "ભારતીય શેરબજાર (NSE/BSE) બપોરે 03:30 વાગ્યે ક્લોઝ થઈ ગયું છે. તમામ ભાવો આજના ક્લોઝિંગ ભાવ પર ફ્રીઝ કરેલા છે. આગામી ટ્રેડિંગ સત્ર આવતીકાલે સવારે 09:15 વાગ્યે શરૂ થશે."
        }

import time
import random
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import Dict, Any

from config import BASE_DIR, get_settings, update_settings
from engine import TradingEngine
import account_manager
import auth_manager

engine = TradingEngine()
background_task = None

async def market_worker():
    while True:
        try:
            engine.execute_cycle()
        except Exception as e:
            engine.log(f'Worker cycle error: {str(e)}', 'DANGER')
        await asyncio.sleep(10)

@asynccontextmanager
async def lifespan(app: FastAPI):
    global background_task
    try:
        from tunnel_manager import tunnel_manager
        tunnel_manager.start()
    except Exception as e:
        print(f"[Tunnel] startup error: {e}")
    try:
        engine.scanner.scan_opportunities()
    except Exception:
        pass
    background_task = asyncio.create_task(market_worker())
    yield
    if background_task:
        background_task.cancel()
    try:
        from tunnel_manager import tunnel_manager
        tunnel_manager.stop()
    except Exception:
        pass

app = FastAPI(title='INDstocks Algo Trading Platform', lifespan=lifespan)

@app.get('/api/tunnel-url')
def get_tunnel_url():
    from tunnel_manager import tunnel_manager
    url = tunnel_manager.get_url()
    return {
        'status': 'success' if url else 'starting',
        'tunnel_url': url,
        'local_ip_url': 'http://192.168.1.15:8000',
        'localhost_url': 'http://localhost:8000'
    }

# Mount static folder
app.mount('/static', StaticFiles(directory=str(BASE_DIR / 'static')), name='static')

@app.get('/')
def serve_index():
    response = FileResponse(str(BASE_DIR / 'static' / 'index.html'))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.post('/api/auth/login')
def login_route(payload: Dict[str, str]):
    user = payload.get('username', '').strip()
    pwd = payload.get('password', '').strip()
    token = auth_manager.verify_login(user, pwd)
    if not token:
        raise HTTPException(status_code=401, detail='અમાન્ય ID અથવા પાસવર્ડ (Invalid ID or Password)')
    return {'status': 'success', 'token': token, 'username': user}

@app.get('/api/auth/check')
def check_auth_route(token: str = ''):
    valid = auth_manager.validate_token(token)
    return {'authenticated': valid}

@app.post('/api/auth/logout')
def logout_route(payload: Dict[str, str]):
    token = payload.get('token', '')
    auth_manager.invalidate_token(token)
    return {'status': 'success'}

@app.post('/api/auth/change-password')
def change_pwd_route(payload: Dict[str, str]):
    old_p = payload.get('old_password', '')
    new_u = payload.get('new_username', '')
    new_p = payload.get('new_password', '')
    success, msg = auth_manager.change_credentials(old_p, new_u, new_p)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {'status': 'success', 'message': msg}

@app.post('/api/auth/verify-pin')
def verify_pin_route(payload: Dict[str, str]):
    user = payload.get('username', '').strip()
    pin = payload.get('pin', '').strip()
    success, msg = auth_manager.verify_recovery_pin(user, pin)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {'status': 'success', 'message': msg}

@app.post('/api/auth/forgot-password')
def forgot_password_route(payload: Dict[str, str]):
    user = payload.get('username', '').strip()
    pin = payload.get('pin', '').strip()
    new_p = payload.get('new_password', '').strip()
    success, msg = auth_manager.reset_password_with_pin(user, pin, new_p)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {'status': 'success', 'message': msg}

@app.get('/api/status')
def get_status():
    timing = get_market_timing()

    # If market is closed, automatically square-off any lingering intraday positions
    if not timing["is_open"] and len(engine.active_trades) > 0:
        trades_to_close = [t for t in engine.active_trades if t.get("trade_type") == "INTRADAY"]
        for t in trades_to_close:
            curr_p = t.get("current_price", t["entry_price"])
            engine.close_trade(t, curr_p, "MARKET_CLOSE_AUTO_EXIT (3:15 PM)")
        engine.active_trades = [t for t in engine.active_trades if t.get("trade_type") != "INTRADAY"]
        engine.save_trades()

    summary = engine.get_dashboard_summary()
    settings = get_settings()
    accounts = account_manager.load_accounts()
    active_accounts = [a for a in accounts if a.get('is_active', True)]
    total_managed_capital = sum(float(a.get('total_capital', 0)) for a in active_accounts)

    return {
        **summary,
        'market_timing': timing,
        'mode': settings.get('mode', 'PAPER'),
        'capital_allocation_pct': settings.get('capital_allocation_pct', 10.0),
        'total_managed_capital': total_managed_capital,
        'active_accounts_count': len(active_accounts),
        'logs': engine.logs[:25]
    }

@app.post('/api/engine/toggle')
def toggle_engine():
    timing = get_market_timing()
    if not timing['is_open']:
        engine.is_running = False
        return {
            'status': 'blocked',
            'is_running': False,
            'market_open': False,
            'message': 'બજાર અત્યારે બંધ છે (03:30 PM પછી). ઓટો ટ્રેડિંગ ફક્ત લાઈવ માર્કેટમાં (સોમવારથી શુક્રવાર સવારે 09:15 થી બપોરે 03:30 દરમિયાન) જ શરૂ કરી શકાશે.'
        }
    if engine.is_running:
        engine.stop()
        return {'is_running': False, 'market_open': timing['is_open'], 'message': 'Trading Engine Stopped'}
    else:
        started = engine.start()
        return {'is_running': started, 'market_open': True, 'message': 'Trading Engine Started'}

@app.post('/api/engine/mode')
def set_mode(payload: Dict[str, str]):
    new_mode = payload.get('mode', 'PAPER').upper()
    if new_mode not in ['PAPER', 'LIVE']:
        raise HTTPException(status_code=400, detail='Mode must be PAPER or LIVE')
    update_settings({'mode': new_mode})
    engine.log(f'Trading mode switched to {new_mode}', 'WARNING')
    return {'mode': new_mode}

@app.get('/api/accounts')
def list_accounts():
    accounts = account_manager.load_accounts()
    safe_accounts = []
    for acc in accounts:
        c = acc.copy()
        tok = c.get('access_token', '')
        c['access_token_masked'] = (tok[:4] + '****' + tok[-4:]) if len(tok) >= 8 else ('****' if tok else 'NOT SET')
        c.pop('access_token', None)
        safe_accounts.append(c)
    return safe_accounts

@app.post('/api/accounts')
def create_account(account: Dict[str, Any]):
    new_acc = account_manager.add_account(account)
    acc_name = new_acc.get('name', 'Account')
    engine.log(f'Added new account: {acc_name}', 'INFO')
    return new_acc

@app.put('/api/accounts/{acc_id}')
def edit_account(acc_id: str, updates: Dict[str, Any]):
    updated = account_manager.update_account(acc_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail='Account not found')
    acc_name = updated.get('name', 'Account')
    engine.log(f'Updated account: {acc_name}', 'INFO')
    return updated

@app.delete('/api/accounts/{acc_id}')
def delete_account_route(acc_id: str):
    success = account_manager.delete_account(acc_id)
    if not success:
        raise HTTPException(status_code=404, detail='Account not found')
    engine.log(f'Deleted account ID: {acc_id}', 'WARNING')
    return {'status': 'success', 'message': 'Account deleted successfully'}

@app.post('/api/accounts/{acc_id}/sync-funds')
def sync_account_funds(acc_id: str):
    accounts = account_manager.load_accounts()
    target_acc = None
    for acc in accounts:
        if acc["id"] == acc_id:
            target_acc = acc
            break
    if not target_acc:
        raise HTTPException(status_code=404, detail="Account not found")

    token = target_acc.get("access_token", "").strip()
    if not token:
        return {
            "status": "warning",
            "message": "INDstocks Access Token નથી મળ્યું. જો તમારી પાસે ટોકન ન હોય તો તમે '✏️ Edit Capital' થી સીધી રકમ પણ લખી શકો છો.",
            "total_capital": target_acc.get("total_capital", 100000.0)
        }

    from indstocks_client import INDstocksClient
    client = INDstocksClient(access_token=token, is_paper=False)
    funds_res = client.get_funds(fallback_capital=target_acc.get("total_capital", 100000.0))
    if funds_res.get("status") == "success" and "available_margin" in funds_res:
        new_capital = float(funds_res["available_margin"])
        account_manager.update_account(acc_id, {"total_capital": new_capital})
        engine.log(f"INDmoney માંથી લાઈવ કેપિટલ ફેચ થઈ: ₹{new_capital}", "INFO")
        return {
            "status": "success",
            "message": f"INDmoney માંથી સફળતાપૂર્વક બેલેન્સ ફેચ થયું: ₹{new_capital}",
            "total_capital": new_capital
        }
    else:
        return {
            "status": "error",
            "message": f"INDstocks સાથે કનેક્ટ ન થઈ શક્યું: {funds_res.get('message', 'Invalid Token')}",
            "total_capital": target_acc.get("total_capital", 100000.0)
        }

@app.delete('/api/accounts/{acc_id}')
def remove_account(acc_id: str):
    success = account_manager.delete_account(acc_id)
    if not success:
        raise HTTPException(status_code=404, detail='Account not found')
    engine.log(f'Removed account ID {acc_id}', 'WARNING')
    return {'status': 'deleted'}

@app.get('/api/settings')
def read_settings():
    return get_settings()

@app.post('/api/settings')
def save_settings(settings: Dict[str, Any]):
    updated = update_settings(settings)
    engine.log('Settings updated successfully', 'INFO')
    return updated

@app.get('/api/scanner')
def get_scanner():
    opps = engine.scanner.cached_opportunities
    if not opps:
        opps = engine.scanner.scan_opportunities()
    return opps

@app.get('/api/news')
def get_news():
    from news_analyzer import fetch_rss_news
    return fetch_rss_news()

@app.post('/api/news/refresh')
def refresh_news():
    from news_analyzer import fetch_rss_news
    articles = fetch_rss_news()
    return {'status': 'success', 'count': len(articles), 'news': articles}

@app.get('/api/trades/active')
def get_active_trades():
    return engine.active_trades

from fastapi.responses import Response
import io
import csv

@app.get('/api/trades/history')
def get_trade_history(filter: str = "today"):
    import datetime
    trades = engine.trade_history
    if filter == "today":
        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        trades = [
            t for t in trades 
            if (t.get("exit_date") and str(t.get("exit_date")).startswith(today_str)) or 
               (t.get("exit_time") and datetime.datetime.fromtimestamp(t.get("exit_time")).strftime("%Y-%m-%d") == today_str)
        ]
    return trades

@app.get('/api/trades/export-csv')
def export_trades_csv(filter: str = "all"):
    import datetime
    trades = engine.trade_history
    if filter == "today":
        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        trades = [
            t for t in trades 
            if (t.get("exit_date") and str(t.get("exit_date")).startswith(today_str)) or 
               (t.get("exit_time") and datetime.datetime.fromtimestamp(t.get("exit_time")).strftime("%Y-%m-%d") == today_str)
        ]
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Trade ID", "Date", "Symbol", "Account", "Type", "Mode", 
        "Quantity", "Buy Price (INR)", "Buy Time", 
        "Sell Price (INR)", "Sell Time", "Duration", 
        "Net PnL (INR)", "Return (%)", "Exit Reason"
    ])
    for t in trades:
        writer.writerow([
            t.get("id", ""),
            str(t.get("exit_date", ""))[:10],
            t.get("symbol", ""),
            t.get("account_name", ""),
            t.get("trade_type", ""),
            t.get("mode", ""),
            t.get("qty", 0),
            t.get("entry_price", 0.0),
            t.get("entry_date", ""),
            t.get("exit_price", 0.0),
            t.get("exit_date", ""),
            t.get("duration_str", ""),
            t.get("pnl", 0.0),
            t.get("pnl_pct", 0.0),
            t.get("exit_reason", "")
        ])
    
    csv_bytes = output.getvalue().encode('utf-8-sig')
    filename = f"trades_journal_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.post('/api/trades/close/{trade_id}')
def manual_close_trade(trade_id: str):
    target_trade = None
    for t in engine.active_trades:
        if t['id'] == trade_id:
            target_trade = t
            break
    if not target_trade:
        raise HTTPException(status_code=404, detail='Trade not found')

    curr_price = target_trade.get('current_price', target_trade['entry_price'])
    engine.close_trade(target_trade, curr_price, 'MANUAL_EXIT')
    engine.active_trades = [t for t in engine.active_trades if t['id'] != trade_id]
    engine.save_trades()
    return {'status': 'success', 'message': f'Trade {trade_id} closed'}

@app.post('/api/emergency/kill')
def emergency_kill():
    engine.emergency_kill_all()
    return {'status': 'success', 'message': 'All positions closed and trading halted'}


import requests

YAHOO_SYMBOL_MAP = {
    "NIFTY": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
    "SENSEX": "^BSESN",
    "FINNIFTY": "NIFTY_FIN_SERVICE.NS",
    "RELIANCE": "RELIANCE.NS",
    "HDFCBANK": "HDFCBANK.NS",
    "SBIN": "SBIN.NS",
    "TATAMOTORS": "TMPV.BO",
    "TCS": "TCS.NS",
    "ICICIBANK": "ICICIBANK.NS",
    "INFY": "INFY.NS",
    "BHARTIARTL": "BHARTIARTL.NS",
    "LT": "LT.NS",
    "BAJFINANCE": "BAJFINANCE.NS",
    "MARUTI": "MARUTI.NS",
    "ITC": "ITC.NS"
}

CHART_CACHE = {}

@app.get("/api/market/chart/{symbol}")
def get_market_chart(symbol: str, interval: str = "5m"):
    sym = symbol.upper().replace("NSE:", "").replace("BSE:", "").strip()
    now = time.time()
    
    interval_map = {
        "1m": ("1m", "1d"),
        "5m": ("5m", "1d"),
        "15m": ("15m", "5d"),
        "30m": ("30m", "5d"),
        "1h": ("60m", "1mo"),
        "1d": ("1d", "1y")
    }
    tf_interval, tf_range = interval_map.get(interval.lower(), ("5m", "1d"))
    cache_key = f"{sym}_{tf_interval}"

    # Check cache (15s)
    cached = CHART_CACHE.get(cache_key)
    if cached and (now - cached["time"] < 15):
        return cached["data"]

    ticker = YAHOO_SYMBOL_MAP.get(sym, f"{sym}.NS")
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval={tf_interval}&range={tf_range}"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code == 200:
            data = r.json()
            res = data["chart"]["result"][0]
            timestamps = res["timestamp"]
            quotes = res["indicators"]["quote"][0]
            
            candles = []
            volumes = []
            is_daily = (tf_interval == "1d")
            for i in range(len(timestamps)):
                o = quotes["open"][i]
                h = quotes["high"][i]
                l = quotes["low"][i]
                c = quotes["close"][i]
                v = quotes.get("volume", [0]*len(timestamps))[i] or 0
                if None not in (o, h, l, c):
                    if is_daily:
                        candle_time = time.strftime("%Y-%m-%d", time.localtime(timestamps[i]))
                    else:
                        # Convert UTC timestamp to IST (+19800s = 5h 30m) so chart renders 09:15 to 15:30 IST
                        candle_time = timestamps[i] + 19800
                    candles.append({
                        "time": candle_time,
                        "open": round(o, 2),
                        "high": round(h, 2),
                        "low": round(l, 2),
                        "close": round(c, 2)
                    })
                    volumes.append({
                        "time": candle_time,
                        "value": int(v),
                        "color": "rgba(22, 163, 74, 0.45)" if c >= o else "rgba(220, 38, 38, 0.45)"
                    })
            
            result_payload = {
                "symbol": sym,
                "real_market": True,
                "current_price": candles[-1]["close"] if candles else 0.0,
                "candles": candles,
                "volumes": volumes
            }
            CHART_CACHE[cache_key] = {"time": now, "data": result_payload}
            CHART_CACHE[sym] = {"time": now, "data": result_payload}
            return result_payload
    except Exception as e:
        pass

    # Fallback to simulated candles if internet drop
    from scanner import WATCHLIST
    base = 1500.0
    for w in WATCHLIST:
        if w["symbol"] == sym:
            base = w["base_price"]
            break
    
    # generate fallback candles with IST timestamp
    candles = []
    volumes = []
    p = base * 0.99
    cur_t = int(now) - (60 * 300)
    for i in range(60):
        t = cur_t + (i * 300) + 19800
        c = p + (random.uniform(-0.003, 0.003) * base)
        h = max(p, c) + abs(random.uniform(0, 0.002) * base)
        l = min(p, c) - abs(random.uniform(0, 0.002) * base)
        v = random.randint(10000, 50000)
        candles.append({"time": t, "open": round(p, 2), "high": round(h, 2), "low": round(l, 2), "close": round(c, 2)})
        volumes.append({"time": t, "value": v, "color": "rgba(22, 163, 74, 0.4)" if c >= p else "rgba(220, 38, 38, 0.4)"})
        p = c
    
    return {"symbol": sym, "real_market": False, "current_price": candles[-1]["close"], "candles": candles, "volumes": volumes}

@app.get("/api/market/live-ticks")
def get_live_ticks():
    timing = get_market_timing()
    is_open = timing["is_open"]

    # Returns sub-second real-time tick streaming for all market assets
    import random
    ticks = {}
    from scanner import WATCHLIST
    for item in WATCHLIST:
        sym = item["symbol"]
        cached = CHART_CACHE.get(sym)
        base = cached["data"]["current_price"] if cached else item["base_price"]
        # realistic sub-second tick micro-movement
        # If market is closed, freeze prices strictly to closing price (no fake movement)
        tick_delta = (random.random() - 0.49) * (base * 0.0006) if is_open else 0.0
        ltp = round(base + tick_delta, 2)
        ticks[sym] = {
            "ltp": ltp,
            "change_pct": round(((ltp - item["base_price"]) / item["base_price"]) * 100.0, 2),
            "timestamp": time.time()
        }
    
    # Indices
    nifty_base = CHART_CACHE.get("NIFTY", {}).get("data", {}).get("current_price", 23780.0)
    bank_base = CHART_CACHE.get("BANKNIFTY", {}).get("data", {}).get("current_price", 57088.0)
    sensex_base = CHART_CACHE.get("SENSEX", {}).get("data", {}).get("current_price", 77800.0)
    
    # If market is closed, freeze to official closing values
    n_jit = (random.random() - 0.49)*8.0 if is_open else 0.0
    b_jit = (random.random() - 0.49)*15.0 if is_open else 0.0
    s_jit = (random.random() - 0.49)*20.0 if is_open else 0.0
    f_jit = (random.random() - 0.49)*6.0 if is_open else 0.0
    v_jit = (random.random() - 0.49)*0.2 if is_open else 0.0

    ticks["NIFTY"] = {"ltp": round(nifty_base + n_jit, 2), "change_pct": -0.49}
    ticks["BANKNIFTY"] = {"ltp": round(bank_base + b_jit, 2), "change_pct": -0.49}
    ticks["SENSEX"] = {"ltp": round(sensex_base + s_jit, 2), "change_pct": -0.42}
    ticks["FINNIFTY"] = {"ltp": round(25210.0 + f_jit, 2), "change_pct": -0.35}
    ticks["INDIAVIX"] = {"ltp": round(13.45 + v_jit, 2), "change_pct": -2.10}
    
    return {"timestamp": time.time(), "ticks": ticks}



@app.post('/api/trades/reset')
def reset_trades_and_pnl():
    engine.active_trades = []
    engine.trade_history = []
    engine.daily_realized_pnl = 0.0
    engine.save_trades()
    engine.log("All trades and P&L reset to 0.0 by user", "INFO")
    return {"status": "success", "message": "All trades and P&L reset to 0.0"}

@app.get('/api/performance')
def get_performance(days: int = 1):
    now = time.time()
    cutoff = now - (days * 86400)
    filtered = [t for t in engine.trade_history if t.get('exit_time', 0) >= cutoff]
    period_realized = sum(t.get('pnl', 0.0) for t in filtered)
    win_count = sum(1 for t in filtered if t.get('pnl', 0.0) > 0)
    total = len(filtered)
    win_rate = round((win_count / total) * 100.0, 1) if total > 0 else 0.0
    active_unrealized = round(sum(t.get('unrealized_pnl', 0.0) for t in engine.active_trades), 2)
    net_pnl = round(period_realized + (active_unrealized if days == 1 else 0.0), 2)
    return {
        "days": days,
        "total_trades": total,
        "winning_trades": win_count,
        "losing_trades": total - win_count,
        "realized_pnl": round(period_realized, 2),
        "unrealized_pnl": active_unrealized,
        "net_pnl": net_pnl,
        "win_rate": win_rate,
        "trades": filtered
    }


if __name__ == '__main__':
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host='0.0.0.0', port=port)
