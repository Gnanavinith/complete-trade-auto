"""
Thin wrapper around python-binance, with synthetic mock fallback so the
engine runs without API keys (USE_MOCK=1). Swap to real client by setting
USE_MOCK=0 and providing BINANCE_API_KEY/SECRET.
"""
import time
import random
import pandas as pd

from app.config import BinanceConfig

KLINE_COLUMNS = [
    "open_time", "open", "high", "low", "close", "volume",
    "close_time", "quote_asset_volume", "trades",
    "taker_buy_base", "taker_buy_quote", "ignore",
]

# synthetic price seeds per symbol (rough real prices)
SEEDS = {
    "BTCUSDT": 43100,
    "ETHUSDT": 2500,
    "SOLUSDT": 144,
    "BNBUSDT": 602,
    "ADAUSDT": 0.45,
}

class MockExecutor:
    """No Binance — generates synthetic klines and fake fills."""
    def __init__(self, cfg: BinanceConfig | None = None):
        self.cfg = cfg
        self.prices: dict[str, float] = {k: v for k, v in SEEDS.items()}
        self._klines: dict[str, pd.DataFrame] = {}

    def _ensure_chain(self, symbol: str, length=200):
        if symbol not in self._klines:
            price = self.prices.get(symbol, 100)
            rows = []
            ts = int(time.time()*1000) - length*15*60*1000
            for i in range(length):
                drift = random.uniform(-0.003, 0.003)
                vol = price * 0.004
                open_p = price
                close_p = price * (1+drift)
                high_p = max(open_p, close_p) + random.uniform(0, vol*0.5)
                low_p = min(open_p, close_p) - random.uniform(0, vol*0.5)
                rows.append([ts, open_p, high_p, low_p, close_p, random.uniform(10, 100)])
                price = close_p
                ts += 15*60*1000
            df = pd.DataFrame(rows, columns=["open_time","open","high","low","close","volume"])
            self._klines[symbol] = df
            self.prices[symbol] = price
        return self._klines[symbol]

    def get_klines_df(self, symbol: str, interval: str, limit: int = 200) -> pd.DataFrame:
        df = self._ensure_chain(symbol, max(limit, 200)).tail(limit).copy()
        # advance one bar on each call to simulate market movement
        last = df.iloc[-1]
        new_price = float(last["close"]) * (1 + random.uniform(-0.004, 0.004))
        self.prices[symbol] = new_price
        new_row = {
            "open_time": int(time.time()*1000),
            "open": float(last["close"]),
            "high": max(float(last["close"]), new_price) + random.uniform(0, new_price*0.001),
            "low": min(float(last["close"]), new_price) - random.uniform(0, new_price*0.001),
            "close": new_price,
            "volume": random.uniform(10, 100),
        }
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True).tail(limit)
        self._klines[symbol] = pd.concat([self._klines[symbol], pd.DataFrame([new_row])], ignore_index=True).tail(500)
        # ensure float dtypes
        for col in ["open","high","low","close","volume"]:
            df[col] = df[col].astype(float)
        return df

    def place_order(self, symbol: str, side: str, qty: float) -> float:
        # simulate slippage ~0.02%
        base = self.prices.get(symbol, 100)
        slip = random.uniform(-0.0002, 0.0002)
        return base * (1+slip)

    def close_position(self, symbol: str, side: str, qty: float) -> float:
        opposite = "short" if side == "long" else "long"
        return self.place_order(symbol, opposite, qty)

    def get_balance(self) -> list[dict]:
        # mock balances
        return [
            {"asset":"USDT","free": 10000.0, "locked": 0.0},
            {"asset":"BTC","free": 0.25, "locked": 0.0},
            {"asset":"ETH","free": 2.5, "locked": 0.0},
        ]


class BinanceExecutor:
    """Real Binance Testnet executor."""
    def __init__(self, cfg: BinanceConfig):
        from binance.client import Client
        self.cfg = cfg
        self.Client = Client
        self.client = Client(cfg.api_key, cfg.api_secret, testnet=cfg.testnet)

    def get_balance(self) -> list[dict]:
        try:
            acc = self.client.get_account()
            bals = acc.get("balances", [])
            out=[]
            for b in bals:
                free=float(b.get("free",0)); locked=float(b.get("locked",0))
                if free>0 or locked>0:
                    out.append({"asset": b["asset"], "free": free, "locked": locked})
            return out
        except Exception as e:
            return [{"asset":"error","free":0,"locked":0,"msg":str(e)}]

    def get_klines_df(self, symbol: str, interval: str, limit: int = 200) -> pd.DataFrame:
        raw = self.client.get_klines(symbol=symbol, interval=interval, limit=limit)
        df = pd.DataFrame(raw, columns=KLINE_COLUMNS)
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)
        return df

    def place_order(self, symbol: str, side: str, qty: float) -> float:
        order_side = self.Client.SIDE_BUY if side == "long" else self.Client.SIDE_SELL
        order = self.client.create_order(
            symbol=symbol, side=order_side, type=self.Client.ORDER_TYPE_MARKET,
            quantity=round(qty, 6),
        )
        fills = order.get("fills", [])
        if fills:
            total_cost = sum(float(f["price"]) * float(f["qty"]) for f in fills)
            total_qty = sum(float(f["qty"]) for f in fills)
            return total_cost / total_qty
        return float(order.get("price") or self.client.get_symbol_ticker(symbol=symbol)["price"])

    def close_position(self, symbol: str, side: str, qty: float) -> float:
        opposite = "short" if side == "long" else "long"
        return self.place_order(symbol, opposite, qty)


def make_executor(cfg: BinanceConfig):
    import os
    if not cfg.api_key or not cfg.api_secret:
        print("[executor] No API keys -> MockExecutor")
        return MockExecutor(cfg)
    # respect explicit USE_MOCK env (if present). If not present, auto is handled in config.use_mock
    use_mock_raw = os.getenv("USE_MOCK")
    # import config lazily to respect computed use_mock, but also honor explicit env
    if use_mock_raw is not None:
        if use_mock_raw.lower() in ("1","true","yes"):
            print("[executor] USE_MOCK=1 -> MockExecutor (synthetic, no Binance calls)")
            return MockExecutor(cfg)
    else:
        # fall back to config.use_mock which auto-detects
        from app.config import config as _cfg
        if _cfg.use_mock:
            print("[executor] use_mock=True -> MockExecutor")
            return MockExecutor(cfg)
    # try real client, verify connectivity with a lightweight ping
    try:
        ex = BinanceExecutor(cfg)
        # quick connectivity test - don't fail startup if unreachable, just fallback
        try:
            ex.client.ping()
            print(f"[executor] Binance Testnet connected (recvWindow={cfg.recv_window})")
        except Exception as e:
            print(f"[executor] Binance ping failed ({e}), falling back to MockExecutor")
            return MockExecutor(cfg)
        return ex
    except Exception as e:
        print(f"[executor] Binance init failed ({e}), falling back to MockExecutor")
        return MockExecutor(cfg)
