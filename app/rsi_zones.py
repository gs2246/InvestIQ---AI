"""Two ways of reading an RSI value. Both are shown wherever RSI is shown.

zone()   Instantaneous reading, from the user's notes page 1. Depends only on
         today's RSI value:
             below 40        Bearish
             40 to 60        Sideways
             above 60        Bullish
         Boundary choice: exactly 40 and exactly 60 are Sideways, so Bullish
         means "RSI > 60", matching System 1's crossover test (rsi > 60).

trend()  Behavioural reading, from the user's notes page 12. Five states:
             RSI above 60       Strong Uptrend    (60-80, and still strong when
                                                   extended past 80)
             RSI below 40       Strong Downtrend  (20-40, and still strong when
                                                   extended below 20)
             RSI 40 to 60       decided by direction (below)
         The strong zones apply by RSI value alone.

         ASSUMPTION, NOT VERBATIM FROM THE NOTES: the notes' bands overlap in
         the middle (40-60), so that tiebreak is a constructed rule. In the
         middle, compare RSI with its value 1 week ago:
             rose by more than 0.5 points     Uptrend
             fell by more than 0.5 points     Downtrend
             moved 0.5 points or less         Sideways
         If it ever needs to change, the constants below are the only place.
"""
import math

import pandas as pd

BEARISH_BELOW = 40.0
BULLISH_ABOVE = 60.0
FLAT_BAND = 0.5

ZONES = ("Bearish", "Sideways", "Bullish")
TRENDS = ("Strong Uptrend", "Uptrend", "Sideways", "Downtrend", "Strong Downtrend")

# How many bars back "1 week ago" is, per timeframe. Monthly bars cannot express
# one week, so the trend reading is not defined for them.
BARS_PER_WEEK = {"daily": 5, "weekly": 1}


def _missing(value) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


def zone(rsi: float | None) -> str | None:
    """Instantaneous RSI zone, or None if RSI is not available yet."""
    if _missing(rsi):
        return None
    if rsi < BEARISH_BELOW:
        return "Bearish"
    if rsi > BULLISH_ABOVE:
        return "Bullish"
    return "Sideways"


def trend(rsi: float | None, rsi_week_ago: float | None) -> str | None:
    """Behavioural RSI trend, or None if it cannot be determined.

    `rsi_week_ago` is only needed in the 40-60 middle; a missing value there
    gives None, while the strong zones never need it.
    """
    if _missing(rsi):
        return None
    if rsi > BULLISH_ABOVE:
        return "Strong Uptrend"
    if rsi < BEARISH_BELOW:
        return "Strong Downtrend"
    if _missing(rsi_week_ago):
        return None
    change = rsi - rsi_week_ago
    if change > FLAT_BAND:
        return "Uptrend"
    if change < -FLAT_BAND:
        return "Downtrend"
    return "Sideways"


def trend_series(rsi: pd.Series, timeframe: str) -> pd.Series:
    """trend() for every bar, comparing with the bar one week earlier.

    Returns an object Series where "not available" is a real None (see
    _label_series for why the dtype is pinned).
    """
    if timeframe not in BARS_PER_WEEK:
        raise ValueError(f"RSI trend is not defined for {timeframe!r} bars")
    week_ago = rsi.shift(BARS_PER_WEEK[timeframe])
    values = [trend(float(a), float(b)) for a, b in zip(rsi, week_ago)]
    return _label_series(values, rsi.index, "rsi_trend")


def zone_series(rsi: pd.Series) -> pd.Series:
    """zone() for every bar (object Series, None where RSI is not available)."""
    values = [zone(float(a)) for a in rsi]
    return _label_series(values, rsi.index, "rsi_zone")


def _label_series(values: list, index: pd.Index, name: str) -> pd.Series:
    # dtype=object must be passed explicitly: pandas 3 otherwise infers a string
    # dtype and silently turns every None into NaN.
    return pd.Series(values, index=index, name=name, dtype=object)
