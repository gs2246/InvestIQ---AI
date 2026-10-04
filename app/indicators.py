"""Pure indicator calculations. No I/O, no state: Series/DataFrame in, Series out.

Every function returns a result aligned to the input index. Positions where the
indicator is not yet defined (not enough history) are NaN.

Conventions (BUILD.md section 9):
- Moving averages are SIMPLE (sma) project-wide. ema() exists as library
  completeness but nothing in the app trades on it.
- RSI uses Wilder's original smoothing, seeded the way TradingView seeds it, so
  values match TradingView / investing.com even in the early years.
- Swing points are N-bar fractals.

Inputs are expected to be ADJUSTED prices (adj_close) with no NaNs; the
functions never modify what they are given.
"""
import numpy as np
import pandas as pd


def sma(series: pd.Series, window: int) -> pd.Series:
    """Simple moving average of the last `window` values (NaN until a full window)."""
    if window < 1:
        raise ValueError("window must be >= 1")
    return series.astype("float64").rolling(window=window, min_periods=window).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    """Exponential moving average, seeded with the SMA of the first `period`
    values (as TradingView does). alpha = 2 / (period + 1)."""
    if period < 1:
        raise ValueError("period must be >= 1")
    values = series.to_numpy(dtype="float64")
    out = np.full(len(values), np.nan)
    if len(values) >= period:
        alpha = 2.0 / (period + 1)
        # plain left-to-right sum (not numpy's pairwise sum) so the seed is
        # exactly reproducible by any straightforward reimplementation
        out[period - 1] = sum(values[:period].tolist()) / period
        for i in range(period, len(values)):
            out[i] = alpha * values[i] + (1.0 - alpha) * out[i - 1]
    return pd.Series(out, index=series.index, name=series.name)


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index with Wilder's smoothing.

    Seed: the first average gain / loss is the plain mean of the first `period`
    price changes, so the first RSI value sits at position `period` (the
    (period+1)-th price). After that each average is
    (previous * (period - 1) + current) / period.

    RSI = 100 when the average loss is 0 (including a perfectly flat series),
    0 when the average gain is 0, otherwise 100 - 100 / (1 + gain / loss).
    This is TradingView's ta.rsi rule.
    """
    if period < 1:
        raise ValueError("period must be >= 1")
    values = series.to_numpy(dtype="float64")
    if np.isnan(values).any():
        raise ValueError("rsi() input contains NaN")
    out = np.full(len(values), np.nan)
    if len(values) <= period:
        return pd.Series(out, index=series.index, name=series.name)

    change = np.diff(values)
    gain = np.where(change > 0, change, 0.0)
    loss = np.where(change < 0, -change, 0.0)

    avg_gain = gain[:period].mean()
    avg_loss = loss[:period].mean()
    out[period] = _rsi_value(avg_gain, avg_loss)
    for i in range(period, len(change)):
        avg_gain = (avg_gain * (period - 1) + gain[i]) / period
        avg_loss = (avg_loss * (period - 1) + loss[i]) / period
        out[i + 1] = _rsi_value(avg_gain, avg_loss)
    return pd.Series(out, index=series.index, name=series.name)


def _rsi_value(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0:
        return 100.0
    if avg_gain == 0:
        return 0.0
    return 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)


def swing_points(df: pd.DataFrame, n: int = 2) -> pd.DataFrame:
    """N-bar fractals on the `high` and `low` columns.

    A bar is a swing high if its high is strictly greater than the highs of the
    `n` bars on each side of it; a swing low if its low is strictly lower than
    the lows of the `n` bars on each side. Returns a DataFrame with boolean
    columns `swing_high` and `swing_low`, same index as `df`.

    The first and last `n` bars can never be swing points (they lack neighbours).
    LOOKAHEAD WARNING: a swing at bar i is only knowable once bar i+n has
    closed. Anything that uses swings to trade must respect that delay.
    """
    if n < 1:
        raise ValueError("n must be >= 1")
    high, low = df["high"], df["low"]
    is_high = pd.Series(True, index=df.index)
    is_low = pd.Series(True, index=df.index)
    for k in range(1, n + 1):
        # shift() yields NaN at the edges and comparisons with NaN are False,
        # which is exactly "no swing without full neighbours".
        is_high &= (high > high.shift(k)) & (high > high.shift(-k))
        is_low &= (low < low.shift(k)) & (low < low.shift(-k))
    return pd.DataFrame({"swing_high": is_high, "swing_low": is_low}, index=df.index)
