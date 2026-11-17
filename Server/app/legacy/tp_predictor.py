"""
Adaptive Take-Profit predictor.

Design (rule-based, ATR + momentum driven — no ML training data needed to start,
but this class is the single seam where a model could later replace the math):

1. INITIAL PREDICTION (predict_tp): when a position opens (or adds a martingale
   step), TP is not a fixed % — it's sized off current volatility (ATR) so it
   tightens in quiet markets and widens in fast ones, then clamped to a sane
   min/max band so a single volatility spike can't set an unreachable target.

2. LIVE REASSESSMENT (reassess): called on every new bar while a position is
   open. It does NOT change TP every bar (that would make the target erratic
   and unreadable) — only every `reassess_every_bars`, and only in two cases:
     - STAGNATION: price has gone `stagnation_bars` without closing distance
       to TP -> shrink TP toward the current price so the trade can realistically
       close instead of tying up martingale capital indefinitely.
     - MOMENTUM: EMA slope + RSI show strong continuation in the trade's favor
       -> extend TP further out to capture more of the move.
   The TP is never moved below a break-even-plus-fees floor.
"""
from dataclasses import dataclass, field
import pandas as pd

from app.indicators import atr, ema_slope_pct, rsi
from app.config import TPConfig


FEE_BUFFER_PCT = 0.001  # ~2x taker fee round trip, kept as a floor above break-even


@dataclass
class TPState:
    current_tp: float
    bars_since_reassess: int = 0
    bars_since_progress: int = 0
    best_progress_pct: float = 0.0


class TPPredictor:
    def __init__(self, cfg: TPConfig):
        self.cfg = cfg

    def predict_tp(self, df: pd.DataFrame, avg_price: float, side: str) -> float:
        """Initial / re-baselined TP after an entry or martingale add."""
        if len(df) < 2:
            tp_pct = self.cfg.min_tp_pct
        else:
            a = atr(df, self.cfg.atr_period).iloc[-1]
            # guard nan on tiny df
            if pd.isna(a):
                tp_pct = self.cfg.min_tp_pct
            else:
                volatility_pct = a / df["close"].iloc[-1]
                tp_pct = self.cfg.base_tp_atr_mult * volatility_pct
                tp_pct = max(self.cfg.min_tp_pct, min(self.cfg.max_tp_pct, tp_pct))
        tp_pct = max(tp_pct, FEE_BUFFER_PCT * 3)

        if side == "long":
            return avg_price * (1 + tp_pct)
        return avg_price * (1 - tp_pct)

    def reassess(self, df: pd.DataFrame, avg_price: float, side: str, state: "TPState") -> "TPState":
        """Call once per new bar. Mutates and returns state with a possibly-updated current_tp."""
        state.bars_since_reassess += 1
        close = df["close"].iloc[-1]

        target_dist = abs(state.current_tp - avg_price)
        progress = (close - avg_price) if side == "long" else (avg_price - close)
        progress_pct = max(0.0, progress / target_dist) if target_dist > 0 else 0.0

        if progress_pct > state.best_progress_pct + 0.02:
            state.best_progress_pct = progress_pct
            state.bars_since_progress = 0
        else:
            state.bars_since_progress += 1

        if state.bars_since_reassess < self.cfg.reassess_every_bars:
            return state
        state.bars_since_reassess = 0

        floor_pct = FEE_BUFFER_PCT * 3
        slope = ema_slope_pct(df["close"], length=9, lookback=5)
        momentum_r = rsi(df["close"]).iloc[-1]

        favorable_momentum = (slope > 0.15 and momentum_r > 55) if side == "long" else \
                              (slope < -0.15 and momentum_r < 45)

        stagnant = state.bars_since_progress >= self.cfg.stagnation_bars

        if stagnant and not favorable_momentum:
            shrink_to_pct = max(floor_pct, (target_dist / avg_price) * 0.6)
            new_tp = avg_price * (1 + shrink_to_pct) if side == "long" else avg_price * (1 - shrink_to_pct)
            if side == "long":
                state.current_tp = min(state.current_tp, max(new_tp, close * (1 + floor_pct)))
            else:
                state.current_tp = max(state.current_tp, min(new_tp, close * (1 - floor_pct)))
            state.bars_since_progress = 0

        elif favorable_momentum and progress_pct > 0.5:
            extend_pct = (target_dist / avg_price) * 1.25
            extend_pct = min(extend_pct, self.cfg.max_tp_pct)
            new_tp = avg_price * (1 + extend_pct) if side == "long" else avg_price * (1 - extend_pct)
            if side == "long":
                state.current_tp = max(state.current_tp, new_tp)
            else:
                state.current_tp = min(state.current_tp, new_tp)

        return state
