"""
Main FastAPI application for Single-Bot BTC Automated Trading System on Delta Exchange India.
Includes full backwards compatibility endpoints for the React dashboard.
"""
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

_ws_clients: list[WebSocket] = []
engine_task: asyncio.Task | None = None
recent_trades_log: list[dict] = []


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
app.add_middleware(CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5174", "http://127.0.0.1:5174", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    }


@app.post("/start")
def start_engine():
    """Start the trading engine loop."""
    engine.is_running = True
    if engine.risk_manager.is_halted and "STOP ALL" in engine.risk_manager.halt_reason:
        engine.risk_manager.is_halted = False
        engine.risk_manager.halt_reason = ""
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


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    _ws_clients.append(ws)
    await ws.send_json({"type": "init", "status": get_status(), "symbols": [engine.btc_symbol]})
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        if ws in _ws_clients:
            _ws_clients.remove(ws)
