"""
Market regime detector.
Classifies market state into: TREND, RANGE, SQUEEZE, CHAOS, or UNKNOWN.
"""
import pandas as pd
from enum import Enum
from app.indicators import adx, bollinger_bands, atr, rolling_percentile


class MarketRegime(Enum):
    TREND = "TREND"
    RANGE = "RANGE"
    SQUEEZE = "SQUEEZE"
    CHAOS = "CHAOS"
    UNKNOWN = "UNKNOWN"


def detect_regime(df: pd.DataFrame, adx_trend_threshold: float = 25.0, adx_range_threshold: float = 20.0) -> MarketRegime:
    """
    Detects the current market regime based on the latest row of the dataframe.
    """
    if df is None or len(df) < 30:
        return MarketRegime.UNKNOWN

    # 1. Check CHAOS: ATR percentile > 90 over past 100 bars
    atr_series = atr(df, period=14)
    atr_pct = rolling_percentile(atr_series, window=100)
    if atr_pct.iloc[-1] >= 90.0:
        return MarketRegime.CHAOS

    # 2. Check SQUEEZE: Bollinger bandwidth at low percentile (< 20th percentile)
    _, _, _, bb_bandwidth = bollinger_bands(df["close"], period=20, std_dev=2.0)
    bb_bw_pct = rolling_percentile(bb_bandwidth, window=100)
    if bb_bw_pct.iloc[-1] <= 20.0:
        return MarketRegime.SQUEEZE

    # 3. Check TREND vs RANGE using ADX(14)
    adx_series = adx(df, period=14)
    current_adx = adx_series.iloc[-1]

    if current_adx >= adx_trend_threshold:
        return MarketRegime.TREND
    elif current_adx <= adx_range_threshold:
        return MarketRegime.RANGE

    # Default if ADX is between range and trend thresholds
    return MarketRegime.RANGE
