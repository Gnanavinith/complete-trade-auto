"""
A single, self-contained Martingale trade sequence.
"""
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
import pandas as pd

from app.config import MartingaleConfig, TPConfig
from app.tp_predictor import TPPredictor, TPState


class BotStatus(Enum):
    OPEN = "OPEN"
    CLOSED_TP = "CLOSED_TP"
    CLOSED_SL = "CLOSED_SL"
    STOPPED = "STOPPED"


@dataclass
class Fill:
    step: int
    price: float
    qty: float
    ts: float


class MartingaleBotInstance:
    def __init__(self, symbol: str, side: str, entry_price: float, entry_qty: float,
                 mg_cfg: MartingaleConfig, tp_cfg: TPConfig, executor):
        self.id = str(uuid.uuid4())[:8]
        self.symbol = symbol
        self.side = side
        self.mg_cfg = mg_cfg
        self.executor = executor
        self.status = BotStatus.OPEN
        self.step = 0
        self.fills: list[Fill] = [Fill(0, entry_price, entry_qty, time.time())]
        self.opened_at = time.time()
        self.closed_at = None
        self.close_reason = None
        self._exit_price = None

        self.tp_predictor = TPPredictor(tp_cfg)
        initial_tp = self.tp_predictor.predict_tp(
            self._seed_df(entry_price), self.avg_price, self.side
        )
        self.tp_state = TPState(current_tp=initial_tp)
        self.sl_price = self._compute_sl()

    @property
    def avg_price(self) -> float:
        total_cost = sum(f.price * f.qty for f in self.fills)
        total_qty = sum(f.qty for f in self.fills)
        return total_cost / total_qty if total_qty else 0

    @property
    def position_qty(self) -> float:
        return sum(f.qty for f in self.fills)

    def _seed_df(self, price: float) -> pd.DataFrame:
        return pd.DataFrame({"open": [price], "high": [price], "low": [price], "close": [price]})

    def _compute_sl(self):
        if not self.mg_cfg.use_emergency_stop:
            return None
        pct = self.mg_cfg.emergency_stop_percent
        return self.avg_price * (1 - pct) if self.side == "long" else self.avg_price * (1 + pct)

    def on_bar(self, df: pd.DataFrame) -> dict:
        if self.status != BotStatus.OPEN:
            return self._snapshot(df)

        close = df["close"].iloc[-1]

        adverse = (close <= self.avg_price * (1 - self.mg_cfg.add_percent)) if self.side == "long" \
            else (close >= self.avg_price * (1 + self.mg_cfg.add_percent))

        if adverse and self.step < self.mg_cfg.max_steps:
            self._add_step(df, close)

        self.tp_state = self.tp_predictor.reassess(df, self.avg_price, self.side, self.tp_state)

        hit_tp = (close >= self.tp_state.current_tp) if self.side == "long" \
            else (close <= self.tp_state.current_tp)
        hit_sl = self.sl_price is not None and (
            (close <= self.sl_price) if self.side == "long" else (close >= self.sl_price)
        )

        if hit_tp:
            self._close(BotStatus.CLOSED_TP, "take_profit", close)
        elif hit_sl:
            self._close(BotStatus.CLOSED_SL, "emergency_stop", close)

        return self._snapshot(df)

    def _add_step(self, df: pd.DataFrame, price: float):
        self.step += 1
        next_qty = self.fills[0].qty * (self.mg_cfg.multiplier ** self.step)
        fill_price = self.executor.place_order(self.symbol, self.side, next_qty)
        self.fills.append(Fill(self.step, fill_price, next_qty, time.time()))
        self.tp_state.current_tp = self.tp_predictor.predict_tp(df, self.avg_price, self.side)
        self.tp_state.bars_since_progress = 0
        self.tp_state.best_progress_pct = 0.0
        self.sl_price = self._compute_sl()

    def _close(self, status: BotStatus, reason: str, price: float):
        try:
            self.executor.close_position(self.symbol, self.side, self.position_qty)
        except Exception:
            pass
        self.status = status
        self.close_reason = reason
        self.closed_at = time.time()
        self._exit_price = price

    def force_stop(self, price: float):
        self._close(BotStatus.STOPPED, "manual_stop", price)

    def realized_pnl(self) -> float:
        if self.status == BotStatus.OPEN or self._exit_price is None:
            return 0.0
        direction = 1 if self.side == "long" else -1
        return direction * (self._exit_price - self.avg_price) * self.position_qty

    def unrealized_pnl(self, current_price: float) -> float:
        direction = 1 if self.side == "long" else -1
        return direction * (current_price - self.avg_price) * self.position_qty

    def _snapshot(self, df: pd.DataFrame | None = None) -> dict:
        # derive a current price for pnl preview if still open
        cur = df["close"].iloc[-1] if df is not None and len(df) else self.avg_price
        return {
            "bot_id": self.id,
            "symbol": self.symbol,
            "side": self.side,
            "status": self.status.value,
            "step": self.step,
            "avg_price": round(self.avg_price, 6),
            "position_qty": round(self.position_qty, 6),
            "tp": round(self.tp_state.current_tp, 6),
            "sl": round(self.sl_price, 6) if self.sl_price else None,
            "opened_at": self.opened_at,
            "closed_at": self.closed_at,
            "close_reason": self.close_reason,
            "pnl": round(self.realized_pnl(), 4) if self.status != BotStatus.OPEN else round(self.unrealized_pnl(cur), 4),
            "stagnation": self.tp_state.bars_since_progress,
            "fills": [{"step": f.step, "price": f.price, "qty": f.qty} for f in self.fills],
        }
