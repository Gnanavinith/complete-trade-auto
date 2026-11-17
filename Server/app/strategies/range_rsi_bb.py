"""
Range Strategy: RSI(14) + Bollinger Band reversion.
Allowed Regimes: [MarketRegime.RANGE]
"""
import pandas as pd
from typing import Optional
from app.strategies.base import BaseStrategy
from app.regime import MarketRegime
from app.indicators import rsi, bollinger_bands


class RangeRsiBbStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(name="RangeRsiBB", allowed_regimes=[MarketRegime.RANGE])

    def vote(self, df_15m: pd.DataFrame, df_1h: Optional[pd.DataFrame] = None) -> float:
        if df_15m is None or len(df_15m) < 30:
            return 0.0

        close = df_15m["close"]
        rsi_val = rsi(close, 14).iloc[-1]
        _, upper, lower, _ = bollinger_bands(close, period=20, std_dev=2.0)
        curr_price = close.iloc[-1]
        curr_upper = upper.iloc[-1]
        curr_lower = lower.iloc[-1]

        score = 0.0

        # Oversold at lower Bollinger band -> Long (mean reversion)
        if rsi_val < 35 and curr_price <= curr_lower * 1.002:
            score = 0.7
        # Overbought at upper Bollinger band -> Short (mean reversion)
        elif rsi_val > 65 and curr_price >= curr_upper * 0.998:
            score = -0.7

        return score
