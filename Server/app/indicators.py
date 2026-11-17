"""
Pure indicator math over a pandas DataFrame with columns: open, high, low, close, volume.
No exchange or strategy logic here — testable in isolation.
"""
import pandas as pd
import numpy as np


def ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False).mean()


def sma(series: pd.Series, length: int) -> pd.Series:
    return series.rolling(window=length).mean()


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        (high - low).abs(),
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return (100 - (100 / (1 + rs))).fillna(50)


def bollinger_bands(series: pd.Series, period: int = 20, std_dev: float = 2.0) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    """Returns (middle, upper, lower, bandwidth)."""
    middle = sma(series, period)
    std = series.rolling(window=period).std()
    upper = middle + (std_dev * std)
    lower = middle - (std_dev * std)
    bandwidth = (upper - lower) / middle.replace(0, np.nan)
    return middle, upper, lower, bandwidth


def adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average Directional Index (ADX)."""
    high, low, close = df["high"], df["low"], df["close"]
    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), minus_dm := down_move, 0.0) # type: ignore

    # proper series conversion
    plus_dm = pd.Series(plus_dm, index=df.index)
    minus_dm = pd.Series(minus_dm, index=df.index)

    tr = pd.concat([
        (high - low).abs(),
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs(),
    ], axis=1).max(axis=1)

    tr_smoothed = tr.ewm(alpha=1/period, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(alpha=1/period, adjust=False).mean() / tr_smoothed.replace(0, np.nan))
    minus_di = 100 * (minus_dm.ewm(alpha=1/period, adjust=False).mean() / tr_smoothed.replace(0, np.nan))

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(alpha=1/period, adjust=False).mean().fillna(0)


def donchian_channels(df: pd.DataFrame, period: int = 20) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Returns (upper_channel, lower_channel, middle_channel)."""
    upper = df["high"].rolling(window=period).max()
    lower = df["low"].rolling(window=period).min()
    middle = (upper + lower) / 2
    return upper, lower, middle


def supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> tuple[pd.Series, pd.Series]:
    """Returns (supertrend_line, direction (+1 for bullish, -1 for bearish))."""
    hl2 = (df["high"] + df["low"]) / 2
    atr_val = atr(df, period)
    upper_basic = hl2 + (multiplier * atr_val)
    lower_basic = hl2 - (multiplier * atr_val)

    close = df["close"]
    n = len(df)
    st = np.zeros(n)
    dir_arr = np.ones(n)

    upper_final = upper_basic.copy()
    lower_final = lower_basic.copy()

    for i in range(1, n):
        if close.iloc[i] > upper_final.iloc[i-1]:
            dir_arr[i] = 1
        elif close.iloc[i] < lower_final.iloc[i-1]:
            dir_arr[i] = -1
        else:
            dir_arr[i] = dir_arr[i-1]
            if dir_arr[i] == 1 and lower_final.iloc[i] < lower_final.iloc[i-1]:
                lower_final.iloc[i] = lower_final.iloc[i-1]
            if dir_arr[i] == -1 and upper_final.iloc[i] > upper_final.iloc[i-1]:
                upper_final.iloc[i] = upper_final.iloc[i-1]

        st[i] = lower_final.iloc[i] if dir_arr[i] == 1 else upper_final.iloc[i]

    return pd.Series(st, index=df.index), pd.Series(dir_arr, index=df.index)


def rolling_percentile(series: pd.Series, window: int = 100) -> pd.Series:
    """Calculates the rolling percentile rank of the current value in the window."""
    return series.rolling(window=window).apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1] * 100, raw=False).fillna(50)


def ema_slope_pct(series: pd.Series, length: int, lookback: int = 3) -> float:
    e = ema(series, length)
    if len(e) < lookback + 1:
        return 0.0
    return float((e.iloc[-1] - e.iloc[-1 - lookback]) / e.iloc[-1 - lookback] * 100)


def crossover(fast: pd.Series, slow: pd.Series) -> bool:
    if len(fast) < 2 or len(slow) < 2:
        return False
    return fast.iloc[-2] <= slow.iloc[-2] and fast.iloc[-1] > slow.iloc[-1]


def crossunder(fast: pd.Series, slow: pd.Series) -> bool:
    if len(fast) < 2 or len(slow) < 2:
        return False
    return fast.iloc[-2] >= slow.iloc[-2] and fast.iloc[-1] < slow.iloc[-1]
