"""Verify app/indicators.py and app/rsi_zones.py.

1. Cross-check production code against INDEPENDENT from-scratch implementations
   (plain Python lists and loops, no pandas / numpy) on all five stocks and all
   three timeframes. RSI, EMA and swing points must match EXACTLY. SMA is
   allowed 1e-9 because pandas' rolling mean updates a running sum while the
   reference re-sums each window, so the last bit can differ.
2. A hand-computed RSI example (worked out on paper, see HAND_EXAMPLE).
3. Invariants: RSI in [0, 100], correct NaN prefix, extremes on monotonic
   input, inputs never mutated.
4. RSI zone / trend: exhaustive grid against a table-driven reference, exact
   boundaries (40, 60, +/-0.5), missing-value handling, label completeness.

Run:  python scripts/verify_indicators.py
"""
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import indicators, prices, rsi_zones  # noqa: E402
from app.stocks import TICKERS  # noqa: E402

failures: list[str] = []
checks = 0


def check(condition: bool, message: str) -> None:
    global checks
    checks += 1
    if not condition:
        failures.append(message)


# ---------------------------------------------------------------------------
# Independent reference implementations (plain Python, deliberately different
# in structure from the production code)
# ---------------------------------------------------------------------------
def ref_sma(xs, window):
    return [None if i + 1 < window else sum(xs[i + 1 - window : i + 1]) / window
            for i in range(len(xs))]


def ref_ema(xs, period):
    out = [None] * len(xs)
    if len(xs) < period:
        return out
    k = 2 / (period + 1)
    prev = sum(xs[:period]) / period
    out[period - 1] = prev
    for i in range(period, len(xs)):
        prev = xs[i] * k + prev * (1 - k)
        out[i] = prev
    return out


def ref_rsi(xs, period):
    out = [None] * len(xs)
    if len(xs) <= period:
        return out
    ups = [max(xs[i] - xs[i - 1], 0.0) for i in range(1, len(xs))]
    downs = [max(xs[i - 1] - xs[i], 0.0) for i in range(1, len(xs))]
    up = sum(ups[:period]) / period
    down = sum(downs[:period]) / period

    def to_rsi(u, d):
        if d == 0:
            return 100.0
        if u == 0:
            return 0.0
        return 100.0 - 100.0 / (1.0 + u / d)

    out[period] = to_rsi(up, down)
    for j in range(period, len(ups)):
        up = (up * (period - 1) + ups[j]) / period
        down = (down * (period - 1) + downs[j]) / period
        out[j + 1] = to_rsi(up, down)
    return out


def ref_rsi_alt(xs, period):
    """Same maths via the algebraically equivalent 100 * U / (U + D)."""
    out = [None] * len(xs)
    ups = [max(xs[i] - xs[i - 1], 0.0) for i in range(1, len(xs))]
    downs = [max(xs[i - 1] - xs[i], 0.0) for i in range(1, len(xs))]
    up = sum(ups[:period]) / period
    down = sum(downs[:period]) / period
    out[period] = 100.0 * up / (up + down) if up + down else 100.0
    for j in range(period, len(ups)):
        up = (up * (period - 1) + ups[j]) / period
        down = (down * (period - 1) + downs[j]) / period
        out[j + 1] = 100.0 * up / (up + down) if up + down else 100.0
    return out


def ref_swings(highs, lows, n):
    hi, lo = [False] * len(highs), [False] * len(highs)
    for i in range(n, len(highs) - n):
        neighbours = [j for j in range(i - n, i + n + 1) if j != i]
        hi[i] = all(highs[i] > highs[j] for j in neighbours)
        lo[i] = all(lows[i] < lows[j] for j in neighbours)
    return hi, lo


def same(prod: pd.Series, ref: list, tol: float = 0.0) -> tuple[bool, float]:
    """Compare a production Series with a reference list (None == NaN)."""
    worst = 0.0
    for p, r in zip(prod.to_list(), ref):
        p_nan = p is None or (isinstance(p, float) and math.isnan(p))
        if p_nan != (r is None):
            return False, math.inf
        if not p_nan:
            worst = max(worst, abs(p - r))
    return worst <= tol, worst


# ---------------------------------------------------------------------------
# 1. Cross-check on real data
# ---------------------------------------------------------------------------
def real_data_checks() -> None:
    print("1. Production vs independent reimplementation (all stocks, all timeframes)")
    worst = {"sma": 0.0, "ema": 0.0, "rsi": 0.0, "rsi_alt": 0.0}
    for symbol in TICKERS:
        for tf in prices.TIMEFRAMES:
            df = prices.load_prices(symbol, tf)
            label = f"{symbol} {tf}"
            before = df.copy()
            close = df["adj_close"]
            xs = close.to_list()

            ok, w = same(indicators.sma(close, 20), ref_sma(xs, 20), tol=1e-9)
            worst["sma"] = max(worst["sma"], w)
            check(ok, f"{label}: sma(20) differs by {w:.3e}")

            ok, w = same(indicators.ema(close, 20), ref_ema(xs, 20))
            worst["ema"] = max(worst["ema"], w)
            check(ok, f"{label}: ema(20) differs by {w:.3e}")

            prod_rsi = indicators.rsi(close, 14)
            ok, w = same(prod_rsi, ref_rsi(xs, 14))
            worst["rsi"] = max(worst["rsi"], w)
            check(ok, f"{label}: rsi(14) differs by {w:.3e}")

            ok, w = same(prod_rsi, ref_rsi_alt(xs, 14), tol=1e-9)
            worst["rsi_alt"] = max(worst["rsi_alt"], w)
            check(ok, f"{label}: rsi(14) vs alternative formula differs by {w:.3e}")

            for n in (1, 2, 3):
                sp = indicators.swing_points(df, n)
                rh, rl = ref_swings(df["high"].to_list(), df["low"].to_list(), n)
                check(sp["swing_high"].to_list() == rh, f"{label}: swing highs n={n}")
                check(sp["swing_low"].to_list() == rl, f"{label}: swing lows n={n}")

            check(df.equals(before), f"{label}: an indicator mutated its input")
    for name, w in worst.items():
        print(f"   max |production - reference|  {name:<8} {w:.3e}")


# ---------------------------------------------------------------------------
# 2. Hand-computed example
# ---------------------------------------------------------------------------
def hand_example() -> None:
    """RSI(3) on closes 10, 11, 10, 12, 13, worked out on paper:

    changes:        +1   -1   +2   +1
    gains:           1    0    2    1
    losses:          0    1    0    0
    seed (first 3): avg_gain = (1+0+2)/3 = 1,  avg_loss = (0+1+0)/3 = 1/3
      RS = 3            -> RSI at the 4th price = 100 - 100/4   = 75
    next change +1: avg_gain = (1*2 + 1)/3 = 1,  avg_loss = (1/3*2 + 0)/3 = 2/9
      RS = 4.5          -> RSI at the 5th price = 100 - 100/5.5 = 81.8181...
    """
    print("2. Hand-computed RSI example")
    out = indicators.rsi(pd.Series([10.0, 11.0, 10.0, 12.0, 13.0]), period=3)
    check(out.iloc[:3].isna().all(), "hand example: first 3 values must be NaN")
    check(abs(out.iloc[3] - 75.0) < 1e-12, f"hand example: expected 75, got {out.iloc[3]}")
    expected = 100 - 100 / 5.5
    check(abs(out.iloc[4] - expected) < 1e-12, f"hand example: expected {expected}, got {out.iloc[4]}")
    print(f"   RSI(3) = {out.iloc[3]:.4f} then {out.iloc[4]:.4f}  (hand: 75 and {expected:.4f})")

    # SMA / EMA by hand: closes 2,4,6,8 -> SMA(2) = nan,3,5,7
    s = indicators.sma(pd.Series([2.0, 4.0, 6.0, 8.0]), 2)
    check(s.isna().tolist() == [True, False, False, False] and s.iloc[1:].tolist() == [3.0, 5.0, 7.0],
          "hand example: sma(2) of 2,4,6,8 should be nan,3,5,7")
    # EMA(2): alpha 2/3, seed = mean(2,4) = 3 -> 3, then 6*2/3+3/3 = 5, 8*2/3+5/3 = 7
    e = indicators.ema(pd.Series([2.0, 4.0, 6.0, 8.0]), 2)
    check(np.allclose(e.iloc[1:].to_numpy(), [3.0, 5.0, 7.0]), "hand example: ema(2) of 2,4,6,8 should be nan,3,5,7")

    # Swing points by hand: highs 1,3,2,5,4  lows 5,3,4,1,2  (n=1)
    df = pd.DataFrame({"high": [1, 3, 2, 5, 4], "low": [5, 3, 4, 1, 2]})
    sp = indicators.swing_points(df, 1)
    check(sp["swing_high"].tolist() == [False, True, False, True, False], "hand example: swing highs")
    check(sp["swing_low"].tolist() == [False, True, False, True, False], "hand example: swing lows")
    # equal neighbours are NOT swings (must strictly exceed)
    flat = indicators.swing_points(pd.DataFrame({"high": [1, 3, 3, 1], "low": [2, 2, 2, 2]}), 1)
    check(not flat["swing_high"].any(), "hand example: a tied high must not be a swing high")


# ---------------------------------------------------------------------------
# 3. Invariants and edge cases
# ---------------------------------------------------------------------------
def invariants() -> None:
    print("3. Invariants and edge cases")
    for symbol in TICKERS:
        for tf in prices.TIMEFRAMES:
            r = indicators.rsi(prices.load_prices(symbol, tf)["adj_close"], 14)
            check(r.iloc[:14].isna().all() and r.iloc[14:].notna().all(), f"{symbol} {tf}: NaN prefix wrong")
            check(((r.dropna() >= 0) & (r.dropna() <= 100)).all(), f"{symbol} {tf}: RSI outside [0, 100]")
    up = indicators.rsi(pd.Series(np.arange(1.0, 60.0)), 14).dropna()
    down = indicators.rsi(pd.Series(np.arange(60.0, 1.0, -1.0)), 14).dropna()
    flat = indicators.rsi(pd.Series([5.0] * 40), 14).dropna()
    check((up == 100).all(), "steadily rising prices must give RSI 100")
    check((down == 0).all(), "steadily falling prices must give RSI 0")
    check((flat == 100).all(), "a flat series gives 100 (TradingView rule: zero average loss)")
    short = indicators.rsi(pd.Series([1.0, 2.0, 3.0]), 14)
    check(short.isna().all() and len(short) == 3, "series shorter than the period must be all NaN")
    for bad in (0, -1):
        for fn in (lambda: indicators.sma(pd.Series([1.0]), bad), lambda: indicators.rsi(pd.Series([1.0]), bad)):
            try:
                fn()
                check(False, f"window/period {bad} should raise ValueError")
            except ValueError:
                check(True, "")
    try:
        indicators.rsi(pd.Series([1.0, float("nan"), 3.0]), 2)
        check(False, "rsi() must reject NaN input")
    except ValueError:
        check(True, "")
    idx = pd.date_range("2020-01-01", periods=30)
    check(indicators.sma(pd.Series(range(30), index=idx, dtype=float), 5).index.equals(idx),
          "indicators must keep the input index")
    print("   done")


# ---------------------------------------------------------------------------
# 4. RSI zone / trend
# ---------------------------------------------------------------------------
def ref_zone(x):
    # table-driven reference: first row whose upper bound is not exceeded
    for upper, label in ((39.999999, "Bearish"), (60.0, "Sideways"), (100.0, "Bullish")):
        if x <= upper:
            return label


def ref_trend(x, prev):
    if x > 60:
        return "Strong Uptrend"
    if x < 40:
        return "Strong Downtrend"
    if prev is None:
        return None
    d = x - prev
    return "Uptrend" if d > 0.5 else "Downtrend" if d < -0.5 else "Sideways"


def zone_trend_checks() -> None:
    print("4. RSI zone and trend")
    grid = [i * 0.25 for i in range(0, 401)]  # 0.00 .. 100.00, exact in binary
    seen_zone, seen_trend = set(), set()
    for x in grid:
        check(rsi_zones.zone(x) == ref_zone(x), f"zone({x}) = {rsi_zones.zone(x)}, expected {ref_zone(x)}")
        seen_zone.add(rsi_zones.zone(x))
        for delta in (-3.0, -0.75, -0.5, -0.25, 0.0, 0.25, 0.5, 0.75, 3.0):
            prev = x - delta
            got, want = rsi_zones.trend(x, prev), ref_trend(x, prev)
            check(got == want, f"trend({x}, prev {prev}) = {got}, expected {want}")
            seen_trend.add(got)
        check(rsi_zones.trend(x, None) == ref_trend(x, None), f"trend({x}, None) wrong")
    check(seen_zone == set(rsi_zones.ZONES), f"zone labels produced {seen_zone} != declared")
    check(seen_trend == set(rsi_zones.TRENDS), f"trend labels produced {seen_trend} != declared")

    for x, want in ((39.99, "Bearish"), (40.0, "Sideways"), (60.0, "Sideways"), (60.01, "Bullish"),
                    (0.0, "Bearish"), (100.0, "Bullish")):
        check(rsi_zones.zone(x) == want, f"boundary zone({x}) expected {want}")
    check(rsi_zones.trend(50.5, 50.0) == "Sideways", "change of exactly +0.5 must be Sideways")
    check(rsi_zones.trend(49.5, 50.0) == "Sideways", "change of exactly -0.5 must be Sideways")
    check(rsi_zones.trend(50.51, 50.0) == "Uptrend", "change of +0.51 must be Uptrend")
    check(rsi_zones.trend(49.49, 50.0) == "Downtrend", "change of -0.51 must be Downtrend")
    check(rsi_zones.trend(95.0, None) == "Strong Uptrend", "extended >80 stays Strong Uptrend by value alone")
    check(rsi_zones.trend(5.0, None) == "Strong Downtrend", "extended <20 stays Strong Downtrend by value alone")
    check(rsi_zones.trend(60.0, 55.0) == "Uptrend", "exactly 60 is the middle band")
    check(rsi_zones.trend(40.0, 45.0) == "Downtrend", "exactly 40 is the middle band")

    nan = float("nan")
    check(rsi_zones.zone(nan) is None and rsi_zones.zone(None) is None, "zone of missing must be None")
    check(rsi_zones.trend(nan, 50.0) is None and rsi_zones.trend(None, None) is None, "trend of missing must be None")
    check(rsi_zones.trend(50.0, nan) is None, "middle band with no week-ago value must be None")
    check(rsi_zones.trend(70.0, nan) == "Strong Uptrend", "strong zone must not need week-ago")

    # Series helpers vs an independent loop, on real data
    for symbol in TICKERS:
        for tf, back in (("weekly", 1), ("daily", 5)):
            r = indicators.rsi(prices.load_prices(symbol, tf)["adj_close"], 14)
            ts, zs = rsi_zones.trend_series(r, tf), rsi_zones.zone_series(r)
            vals = r.to_list()
            for i, v in enumerate(vals):
                nan_v = isinstance(v, float) and math.isnan(v)
                prev = vals[i - back] if i >= back else None
                prev = None if prev is not None and math.isnan(prev) else prev
                want_t = None if nan_v else ref_trend(v, prev)
                want_z = None if nan_v else ref_zone(v)
                if ts.iloc[i] is not want_t and ts.iloc[i] != want_t:
                    check(False, f"{symbol} {tf} trend_series[{i}] = {ts.iloc[i]!r}, expected {want_t!r}")
                    break
                if zs.iloc[i] is not want_z and zs.iloc[i] != want_z:
                    check(False, f"{symbol} {tf} zone_series[{i}] = {zs.iloc[i]!r}, expected {want_z!r}")
                    break
            else:
                check(True, "")
            # None must stay None (pandas 3 trap: None silently becomes NaN in string columns)
            check(ts.iloc[0] is None and zs.iloc[0] is None, f"{symbol} {tf}: missing label is not a real None")
    try:
        rsi_zones.trend_series(pd.Series([50.0, 51.0]), "monthly")
        check(False, "trend_series must refuse monthly bars")
    except ValueError:
        check(True, "")
    print("   done")


def show_latest() -> None:
    print("5. Latest completed weekly values (for your TradingView spot-check)")
    print(f"   {'stock':<14}{'week ending':<13}{'adj close':>10}{'SMA(20)':>10}{'RSI(14)':>9}  zone / trend")
    for symbol in TICKERS:
        df = prices.load_prices(symbol, "weekly")
        close = df["adj_close"]
        r = indicators.rsi(close, 14)
        s = indicators.sma(close, 20)
        z = rsi_zones.zone_series(r).iloc[-1]
        t = rsi_zones.trend_series(r, "weekly").iloc[-1]
        print(f"   {symbol:<14}{df['date'].iloc[-1]:%Y-%m-%d}   {close.iloc[-1]:>10.2f}{s.iloc[-1]:>10.2f}{r.iloc[-1]:>9.2f}  {z} / {t}")


def main() -> int:
    real_data_checks()
    hand_example()
    invariants()
    zone_trend_checks()
    show_latest()
    print()
    if failures:
        print(f"FAILURES ({len(failures)}):")
        for line in failures[:40]:
            print(f"  {line}")
        return 1
    print(f"All {checks} checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
