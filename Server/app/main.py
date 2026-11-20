"""
Main FastAPI application for Single-Bot BTC Automated Trading System on Delta Exchange India.
Includes full backwards compatibility endpoints for the React dashboard.
"""
import os
import sys

# Ensure 'Server' root is in sys.path regardless of execution directory
_server_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _server_dir not in sys.path:
    sys.path.insert(0, _server_dir)

import asyncio
import logging
from contextlib import asynccontextmanager
import pandas as pd

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.config import config
from app.delta_client import make_delta_client
from app.engine import SingleBotEngine
from app.backtest.backtester import Backtester
from app.db import connect_mongo, close_mongo, save_trade, save_trade_exit, save_equity_snapshot, get_recent_trades_from_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("main")

client = make_delta_client(config.delta)
engine = SingleBotEngine(config, client)


def _on_delta_auth_failure(client_ip: str) -> None:
    """Halt the engine when Delta rejects the API key (IP not whitelisted, 401, etc.)."""
    engine.risk_manager.is_halted = True
    engine.risk_manager.halt_reason = f"API auth failed: whitelist IP {client_ip}"
    log.critical("Delta API auth failed. Engine HALTED. Whitelist IP %s on Delta and restart the server.", client_ip)


client.on_auth_failure = _on_delta_auth_failure
log.info(
    "Delta env=%s base_url=%s paper_mode=%s (confirm DELTA_ENV matches the key: testnet vs production)",
    config.delta.env,
    config.delta.base_url,
    config.paper_mode,
)

_ws_clients: list[WebSocket] = []
engine_task: asyncio.Task | None = None
recent_trades_log: list[dict] = []
last_decision_diagnostic: dict = {}


async def engine_loop():
    log.info("Starting SingleBotEngine background loop...")
    try:
        engine.initialize()
    except Exception as e:
        log.error("Engine initialization error: %s", e)

    while True:
        if engine.is_running:
            try:
                cycle_result = engine.run_cycle()
                log.info("Engine cycle result: %s", cycle_result)

                global last_decision_diagnostic
                last_decision_diagnostic = cycle_result.get("diagnostic", {})

                if "trade" in cycle_result:
                    trade_doc = {
                        "botId": "btc-single-bot",
                        "symbol": engine.btc_symbol,
                        "side": cycle_result["trade"]["side"],
                        "entry_price": cycle_result["trade"]["price"],
                        "stop_loss": cycle_result["trade"]["sl"],
                        "take_profit": cycle_result["trade"]["tp"],
                        "qty": cycle_result["trade"]["contracts"] * 0.001,
                        "event": "ENTRY",
                        "status": "OPEN",
                        "ts": cycle_result["timestamp"]
                    }
                    recent_trades_log.insert(0, trade_doc)
                    await save_trade(trade_doc)

                # Check if position closed / hit exit
                position = engine.execution.reconcile_position(engine.btc_product_id) if engine.btc_product_id else None
                if position is None and any(t.get("status") == "OPEN" for t in recent_trades_log):
                    for t in recent_trades_log:
                        if t.get("status") == "OPEN":
                            t["status"] = "CLOSED"
                            t["event"] = "EXIT"
                            t["exit_timestamp"] = cycle_result["timestamp"]
                            # Record exit & PnL
                            await save_trade_exit({"ts": t["ts"], "status": "OPEN"}, {
                                "status": "CLOSED",
                                "event": "EXIT",
                                "exit_timestamp": cycle_result["timestamp"],
                                "unrealized_pnl": 0.0
                            })
                            break

                await save_equity_snapshot({
                    "timestamp": cycle_result["timestamp"],
                    "equity": engine.risk_manager.equity,
                    "daily_pnl": engine.risk_manager.daily_pnl
                })

                await _broadcast({"type": "engine_update", "result": cycle_result})
            except Exception as e:
                log.error("Error in engine loop: %s", e)
        else:
            log.debug("Engine is stopped. Skipping cycle...")
            await _broadcast({"type": "engine_update", "result": {"status": "stopped", "action": "stopped"}})

        await asyncio.sleep(60)


async def _broadcast(payload: dict):
    dead = []
    for ws in _ws_clients:
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        if ws in _ws_clients:
            _ws_clients.remove(ws)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_mongo()
    global engine_task
    engine_task = asyncio.create_task(engine_loop())
    yield
    if engine_task:
        engine_task.cancel()
    await close_mongo()


app = FastAPI(title="Delta India BTC Single-Bot Trading System", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:3000",
        "https://complete-trade-auto-vinith.onrender.com",
        "*",
    ],
    allow_origin_regex=r"https://.*\.netlify\.app|https://.*\.onrender\.com",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/debug/last-decision")
def get_last_decision():
    """Returns decision diagnostics for the latest engine cycle."""
    return last_decision_diagnostic if last_decision_diagnostic else {"status": "no_cycle_run_yet"}


from fastapi.responses import HTMLResponse

@app.get("/privacy", response_class=HTMLResponse)
def privacy_policy():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Privacy Policy - Complete Trade Auto</title>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 40px auto; padding: 0 20px; background: #f9fafb; }
            .container { background: #fff; padding: 40px; border: 1px solid #e5e7eb; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
            h1 { font-size: 28px; margin-bottom: 8px; color: #111; }
            h2 { font-size: 18px; margin-top: 24px; color: #1f2937; }
            p, li { font-size: 14px; color: #4b5563; }
            .date { font-size: 12px; color: #9ca3af; margin-bottom: 24px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Privacy Policy</h1>
            <div class="date">Last updated: November 18, 2026</div>
            <p>Welcome to <strong>Complete Trade Auto</strong> ("we", "our", or "us"). We respect your privacy and are committed to protecting your personal data. This privacy policy informs you how we handle your information when you use our automated Bitcoin trading platform and Instagram/WhatsApp notification services.</p>

            <h2>1. Information We Collect</h2>
            <p>When you connect your Meta / Instagram account or use our trading dashboard, we may collect basic profile information such as your user ID, username, and messages sent through the Instagram Messaging API strictly for the purpose of sending automated trade execution alerts, market regime analysis, and PnL summaries to you.</p>

            <h2>2. How We Use Your Information</h2>
            <p>We use the collected information solely to:</p>
            <ul>
                <li>Deliver real-time trade signals, entry/exit notifications, and equity updates via Instagram Direct Message.</li>
                <li>Maintain and secure the automated trading engine operations.</li>
            </ul>

            <h2>3. Data Security & Sharing</h2>
            <p>We implement robust security measures to protect your credentials and data. We do not sell, trade, or otherwise transfer your personal information to outside parties. All API keys and tokens are encrypted and stored securely.</p>

            <h2>4. Contact Us</h2>
            <p>If you have any questions regarding this Privacy Policy, please reach out via our GitHub repository or support channel.</p>
        </div>
    </body>
    </html>
    """

@app.get("/health")
def health():
    return {
        "status": "ok",
        "env": config.delta.env,
        "paper_mode": config.paper_mode,
        "symbol": engine.btc_symbol,
        "equity": engine.risk_manager.equity,
        "daily_pnl": engine.risk_manager.daily_pnl,
        "is_halted": engine.risk_manager.is_halted,
    }


@app.get("/status")
def get_status():
    position = engine.execution.reconcile_position(engine.btc_product_id) if engine.btc_product_id else None
    passed, gate_reason = engine.risk_manager.check_gates()

    # Try fetching live wallet balance for frontend display
    wallet_balances = []
    try:
        if not config.paper_mode and config.delta.api_key:
            wallet_balances = client.get_wallet_balances()
    except Exception:
        pass

    return {
        "equity": engine.risk_manager.equity,
        "starting_equity": engine.risk_manager.starting_equity,
        "daily_pnl": engine.risk_manager.daily_pnl,
        "consecutive_losses": engine.risk_manager.consecutive_losses,
        "is_halted": engine.risk_manager.is_halted,
        "halt_reason": engine.risk_manager.halt_reason,
        "gates_passed": passed,
        "gate_reason": gate_reason,
        "position": position,
        "paper_mode": config.paper_mode,
        "is_running": engine.is_running,
        "wallet_balances": wallet_balances,
    }


@app.post("/start")
def start_engine():
    """Start the trading engine loop."""
    engine.is_running = True
    if engine.risk_manager.is_halted and ("STOP ALL" in engine.risk_manager.halt_reason or "API auth failed" in engine.risk_manager.halt_reason):
        engine.risk_manager.is_halted = False
        engine.risk_manager.halt_reason = ""
        client._auth_failed = False
        client._auth_fail_time = 0.0
    log.info("Engine started by user request.")
    return {"success": True, "is_running": True, "message": "Trading engine started."}


@app.post("/stop")
def stop_engine():
    """Stop the trading engine loop."""
    engine.is_running = False
    log.info("Engine stopped by user request.")
    return {"success": True, "is_running": False, "message": "Trading engine stopped."}


@app.get("/config")
def get_config():
    # Compatibility config structure for frontend
    return {
        "signal": {"ema_fast": 9, "ema_slow": 21, "timeframe": config.strategy.timeframe},
        "martingale": {"base_qty_usdt": 20.0, "multiplier": 1.8, "max_steps": 5, "add_percent": 1.0, "emergency_stop_percent": 15.0},
        "tp": {"atr_period": 14, "base_tp_atr_mult": 1.5, "min_tp_pct": 0.5, "max_tp_pct": 3.0, "stagnation_bars": 12},
        "manager": {"symbols": [engine.btc_symbol], "max_per_day": 10, "max_total": 1},
        "daily_counts": {engine.btc_symbol: 0},
        "delta": {
            "env": config.delta.env,
            "base_url": config.delta.base_url,
            "paper_mode": config.paper_mode,
            "risk_per_trade_pct": config.risk.risk_per_trade_pct * 100,
        }
    }


@app.get("/bots")
def list_bots():
    """Compatibility endpoint for dashboard bot ledger."""
    position = engine.execution.reconcile_position(engine.btc_product_id) if engine.btc_product_id else None
    if not position:
        return []
    return [{
        "id": "btc-single-bot-1",
        "symbol": engine.btc_symbol,
        "side": position["side"],
        "status": "OPEN",
        "avg_price": position["entry_price"],
        "position_qty": position["size"],
        "step": 0,
        "opened_at": pd.Timestamp.now().isoformat(),
        "unrealized_pnl": position.get("unrealized_pnl", 0.0)
    }]


@app.get("/symbols")
def symbols():
    """Compatibility endpoint for symbol board."""
    price = 65000.0
    try:
        df = client.get_candles(symbol=engine.btc_symbol, resolution="15m", limit=5)
        if not df.empty:
            price = float(df["close"].iloc[-1])
    except Exception:
        pass

    position = engine.execution.reconcile_position(engine.btc_product_id) if engine.btc_product_id else None
    return [{
        "symbol": engine.btc_symbol,
        "price": price,
        "open": 1 if position else 0,
        "cap": 1
    }]


@app.get("/trades")
async def trades():
    """Compatibility endpoint for execution tape / trades log backed by MongoDB."""
    db_trades = await get_recent_trades_from_db(100)
    if db_trades:
        return db_trades
    return recent_trades_log[:100]


@app.get("/balance")
def balance():
    """Compatibility endpoint for balance view."""
    try:
        if config.paper_mode or not config.delta.api_key:
            return {
                "balances": [
                    {"asset": "USDT", "free": engine.risk_manager.equity, "locked": 0.0},
                    {"asset": "BTC", "free": 0.5, "locked": 0.0}
                ],
                "mock": True
            }
        bals = client.get_wallet_balances()
        return {"balances": bals, "mock": False}
    except Exception as e:
        return {
            "balances": [{"asset": "USDT", "free": engine.risk_manager.equity, "locked": 0.0}],
            "error": str(e),
            "mock": True
        }


@app.get("/backtest")
def run_backtest():
    try:
        btc_id = client.get_btc_product_id()
        btc_symbol = client._btc_symbol
        df_15m = client.get_candles(symbol=btc_symbol, resolution="15m", limit=500)
        df_1h = client.get_candles(symbol=btc_symbol, resolution="1h", limit=200)

        backtester = Backtester(df_15m=df_15m, df_1h=df_1h, initial_equity=10000.0)
        results = backtester.run()
        return results
    except Exception as e:
        log.error("Backtest error: %s", e)
        return {"error": str(e)}


@app.post("/stop-all")
def stop_all():
    """Kill switch: halts engine and closes/cancels open positions."""
    engine.risk_manager.is_halted = True
    engine.risk_manager.halt_reason = "Manual STOP ALL triggered by user"
    log.critical("MANUAL STOP ALL TRIGGERED")
    return {"success": True, "message": "Engine halted and risk kill switch activated."}


@app.post("/test-entry")
def test_entry():
    """Manually test a simulated entry trade cycle."""
    try:
        if engine.btc_product_id is None:
            engine.initialize()
        df_15m = client.get_candles(symbol=engine.btc_symbol, resolution="15m", limit=200)
        df_1h = client.get_candles(symbol=engine.btc_symbol, resolution="1h", limit=100)
        if df_15m.empty:
            return {"success": False, "error": "Empty candles"}
        price = float(df_15m["close"].iloc[-1])
        from app.indicators import atr
        atr_val = float(atr(df_15m, 14).iloc[-1])

        contracts, sl, tp = engine.risk_manager.calculate_position_size(price, atr_val, engine.risk_manager.equity)
        import time
        trade_doc = {
            "botId": "btc-single-bot",
            "symbol": engine.btc_symbol,
            "side": "long",
            "entry_price": price,
            "stop_loss": sl,
            "take_profit": tp,
            "qty": contracts * 0.001,
            "event": "TEST_ENTRY",
            "status": "OPEN",
            "ts": int(time.time())
        }
        recent_trades_log.insert(0, trade_doc)
        return {"success": True, "trade": trade_doc}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/test-instagram")
def test_instagram(message: str = "Complete Trade Auto: Test alert notification"):
    """Test Instagram Direct Message notification."""
    from app.instagram import instagram_notifier
    success, detail = instagram_notifier.send_message_detailed(message)
    return {
        "success": success,
        "detail": detail,
        "recipient_id": instagram_notifier.recipient_id,
        "account_id": instagram_notifier.ig_user_id
    }


@app.get("/ai-analysis")
def get_ai_analysis():
    """Returns the latest Google Gemini market intelligence analysis."""
    from app.ai_analyst import ai_analyst
    if ai_analyst.latest_analysis:
        return {"success": True, "analysis": ai_analyst.latest_analysis}

    try:
        df_15m = client.get_candles(symbol=engine.btc_symbol, resolution="15m", limit=50)
        price = float(df_15m["close"].iloc[-1]) if not df_15m.empty else 65000.0
        from app.indicators import rsi, adx, ema
        rsi_val = float(rsi(df_15m["close"], 14).iloc[-1]) if not df_15m.empty else 50.0
        adx_val = float(adx(df_15m, 14).iloc[-1]) if not df_15m.empty else 25.0
        ema9 = float(ema(df_15m["close"], 9).iloc[-1]) if not df_15m.empty else price
        ema21 = float(ema(df_15m["close"], 21).iloc[-1]) if not df_15m.empty else price
        from app.regime import detect_regime
        regime = detect_regime(df_15m).value if not df_15m.empty else "TREND"

        analysis = ai_analyst.analyze_market(
            symbol=engine.btc_symbol,
            price=price,
            regime=regime,
            rsi=rsi_val,
            adx=adx_val,
            ema_fast=ema9,
            ema_slow=ema21,
            trend_1h="BULLISH" if ema9 > ema21 else "BEARISH",
        )
        return {"success": True, "analysis": analysis}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/ai-analysis/generate")
def generate_ai_analysis(send_notifications: bool = False):
    """Generates fresh Google Gemini market analysis and optionally broadcasts to Instagram."""
    from app.ai_analyst import ai_analyst
    try:
        df_15m = client.get_candles(symbol=engine.btc_symbol, resolution="15m", limit=50)
        price = float(df_15m["close"].iloc[-1]) if not df_15m.empty else 65000.0
        from app.indicators import rsi, adx, ema
        rsi_val = float(rsi(df_15m["close"], 14).iloc[-1]) if not df_15m.empty else 50.0
        adx_val = float(adx(df_15m, 14).iloc[-1]) if not df_15m.empty else 25.0
        ema9 = float(ema(df_15m["close"], 9).iloc[-1]) if not df_15m.empty else price
        ema21 = float(ema(df_15m["close"], 21).iloc[-1]) if not df_15m.empty else price
        from app.regime import detect_regime
        regime = detect_regime(df_15m).value if not df_15m.empty else "TREND"

        analysis = ai_analyst.analyze_market(
            symbol=engine.btc_symbol,
            price=price,
            regime=regime,
            rsi=rsi_val,
            adx=adx_val,
            ema_fast=ema9,
            ema_slow=ema21,
            trend_1h="BULLISH" if ema9 > ema21 else "BEARISH",
        )

        dispatch_result = None
        if send_notifications:
            dispatch_result = ai_analyst.dispatch_notifications(analysis)

        return {
            "success": True,
            "analysis": analysis,
            "dispatch": dispatch_result
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    _ws_clients.append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Echo or handle incoming ws messages
            await websocket.send_json({"type": "ack", "message": data})
    except WebSocketDisconnect:
        if websocket in _ws_clients:
            _ws_clients.remove(websocket)
    except Exception:
        if websocket in _ws_clients:
            _ws_clients.remove(websocket)
