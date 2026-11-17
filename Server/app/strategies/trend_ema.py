"""
Baseline Trend Strategy: 1h EMA 50/200 higher-timeframe trend filter + 15m EMA 9/21 crossover & Supertrend confirmation.
Allowed Regimes: [MarketRegime.TREND]
"""
import pandas as pd
from typing import Optional
from app.strategies.base import BaseStrategy
from app.regime import MarketRegime
from app.indicators import ema, crossover, crossunder, supertrend


class TrendEmaStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(name="TrendEMA", allowed_regimes=[MarketRegime.TREND])

    def vote(self, df_15m: pd.DataFrame, df_1h: Optional[pd.DataFrame] = None) -> float:
        if df_15m is None or len(df_15m) < 30:
            return 0.0

        # 1. 15m EMA 9/21
        fast = ema(df_15m["close"], 9)
        slow = ema(df_15m["close"], 21)

        is_bullish_cross = crossover(fast, slow)
        is_bearish_cross = crossunder(fast, slow)
        is_bullish_aligned = fast.iloc[-1] > slow.iloc[-1]
        is_bearish_aligned = fast.iloc[-1] < slow.iloc[-1]

        # 2. Supertrend confirmation on 15m
        _, st_dir = supertrend(df_15m, period=10, multiplier=3.0)
        st_bullish = st_dir.iloc[-1] == 1
        st_bearish = st_dir.iloc[-1] == -1

        # 3. Higher timeframe (1h) trend filter if available
        htf_bullish = True
        htf_bearish = True
        if df_1h is not None and len(df_1h) >= 50:
            h_fast = ema(df_1h["close"], 50)
            h_slow = ema(df_1h["close"], 200) if len(df_1h) >= 200 else ema(df_1h["close"], 50)
            htf_bullish = h_fast.iloc[-1] >= h_slow.iloc[-1]
            htf_bearish = h_fast.iloc[-1] <= h_slow.iloc[-1]

        score = 0.0

        # Long vote
        if (is_bullish_cross or is_bullish_aligned) and st_bullish and htf_bullish:
            score = 0.8 if is_bullish_cross else 0.5
        # Short vote
        elif (is_bearish_cross or is_bearish_aligned) and st_bearish and htf_bearish:
            score = -0.8 if is_bearish_cross else -0.5

        return score
