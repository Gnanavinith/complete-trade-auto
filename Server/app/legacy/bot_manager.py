"""
Owns every MartingaleBotInstance across every symbol.
"""
from collections import defaultdict
from datetime import datetime, timezone
import pandas as pd

from app.config import AppConfig
from app.martingale_bot import MartingaleBotInstance, BotStatus


class BotManager:
    def __init__(self, cfg: AppConfig, executor):
        self.cfg = cfg
        self.executor = executor
        self.bots: dict[str, list[MartingaleBotInstance]] = defaultdict(list)
        self._daily_count: dict[tuple[str, str], int] = defaultdict(int)

    def _today_key(self, symbol: str) -> tuple[str, str]:
        return (symbol, datetime.now(timezone.utc).strftime("%Y-%m-%d"))

    def open_bots(self, symbol: str | None = None) -> list[MartingaleBotInstance]:
        if symbol:
            return [b for b in self.bots[symbol] if b.status == BotStatus.OPEN]
        out = []
        for s in self.bots:
            out.extend(b for b in self.bots[s] if b.status == BotStatus.OPEN)
        return out

    def on_signal(self, symbol: str, side: str, df: pd.DataFrame, amount_usdt: float | None = None, amount_mode: str = "base") -> MartingaleBotInstance | None:
        key = self._today_key(symbol)
        if self._daily_count[key] >= self.cfg.manager.max_concurrent_bots_per_symbol_per_day:
            return None

        total_open = len(self.open_bots())
        if total_open >= self.cfg.manager.max_total_concurrent_bots:
            return None

        entry_price = float(df["close"].iloc[-1])
        # priority: explicit amount_usdt from API > direct qty config > default USDT
        if amount_usdt is not None and amount_usdt > 0:
            if amount_mode == "total":
                # total capital available -> derive base so total exposure fits
                mult = self.cfg.martingale.multiplier
                max_steps = self.cfg.martingale.max_steps
                # total = base * sum(mult^i)  => base = total / sum
                total_mult = sum(mult ** i for i in range(max_steps+1))
                base_usdt = amount_usdt / total_mult if total_mult else amount_usdt
                entry_qty = base_usdt / entry_price
            else:
                # base mode: amount is first order size
                entry_qty = amount_usdt / entry_price
        elif getattr(self.cfg.martingale, "base_qty_direct", None) not in (None, ""):
            try:
                entry_qty = float(self.cfg.martingale.base_qty_direct)
            except Exception:
                entry_qty = self.cfg.martingale.base_qty_usdt / entry_price
        else:
            entry_qty = self.cfg.martingale.base_qty_usdt / entry_price
        
        # Minimum notional check for Binance (10 USDT for most pairs)
        min_notional = 10.0
        if entry_qty * entry_price < min_notional:
            # scale up to minimum notional
            entry_qty = min_notional / entry_price
        
        fill_price = self.executor.place_order(symbol, side, entry_qty)

        bot = MartingaleBotInstance(
            symbol=symbol, side=side, entry_price=fill_price, entry_qty=entry_qty,
            mg_cfg=self.cfg.martingale, tp_cfg=self.cfg.tp, executor=self.executor,
        )
        self.bots[symbol].append(bot)
        self._daily_count[key] += 1
        return bot

    def on_bar(self, symbol: str, df: pd.DataFrame) -> list[dict]:
        return [bot.on_bar(df) for bot in self.open_bots(symbol)]

    def all_snapshots(self, df_map: dict | None = None) -> list[dict]:
        out = []
        for symbol, symbol_bots in self.bots.items():
            df = df_map.get(symbol) if df_map else None
            out.extend(b._snapshot(df) for b in symbol_bots)
        # newest first
        out.sort(key=lambda x: x["opened_at"], reverse=True)
        return out

    def stop_bot(self, bot_id: str, last_price: float) -> bool:
        for symbol_bots in self.bots.values():
            for b in symbol_bots:
                if b.id == bot_id and b.status == BotStatus.OPEN:
                    b.force_stop(last_price or b.avg_price)
                    return True
        return False

    def daily_counts(self) -> dict:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return {sym: self._daily_count[(sym, today)] for sym in self.cfg.manager.symbols}
