"""Integrity checks on the downloaded price data.

Daily files (every stock):
  1. no empty values            4. OHLC sanity (low <= open/close <= high, > 0)
  2. no duplicate dates         5. gaps between trading days
  3. dates strictly ascending   6. corporate-action ratio shifts

Weekly / monthly files (every stock):
  OHLC sanity, no nulls/duplicates, and a cross-check against the daily file
  (volume totals, first open, last close and last adj_close must match).

FAIL lines make the script exit with code 1. INFO lines are listed for a human
to read but are not failures.

Run:  python scripts/verify_data.py
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.stocks import TICKERS  # noqa: E402

PRICE_COLS = ["open", "high", "low", "close", "adj_close"]
GAP_DAYS = 7           # calendar days between consecutive trading days
BIG_MOVE = 0.20        # a one-day close-to-close move this large is suspicious...
VOLUME_SPIKE = 3.0     # ...unless volume is this many times the prior 20-day median
RATIO_INFO = 0.001     # adj_close/close step above this = a dividend-sized adjustment
RATIO_FAIL = 0.10      # a step this large cannot be a normal dividend


def load(timeframe: str, symbol: str) -> pd.DataFrame:
    df = pd.read_csv(ROOT / "data" / timeframe / f"{symbol}.csv")
    df["date"] = pd.to_datetime(df["date"])
    return df


def basic_checks(df: pd.DataFrame, label: str, fails: list) -> None:
    nulls = int(df.isna().sum().sum())
    if nulls:
        fails.append(f"{label}: {nulls} empty values")
    dups = int(df["date"].duplicated().sum())
    if dups:
        fails.append(f"{label}: {dups} duplicate dates")
    if not df["date"].is_monotonic_increasing:
        fails.append(f"{label}: dates are not in ascending order")
    bad = (
        (df[PRICE_COLS] <= 0).any(axis=1)
        | (df["low"] > df[["open", "close"]].min(axis=1))
        | (df["high"] < df[["open", "close"]].max(axis=1))
        | (df["low"] > df["high"])
    )
    if bad.any():
        sample = ", ".join(df.loc[bad, "date"].dt.strftime("%Y-%m-%d").head(5))
        fails.append(f"{label}: {int(bad.sum())} candles fail OHLC sanity (e.g. {sample})")
    if (df["volume"] < 0).any():
        fails.append(f"{label}: negative volume")


def check_daily(symbol: str, fails: list, info: list) -> pd.DataFrame:
    df = load("daily", symbol)
    basic_checks(df, f"{symbol} daily", fails)

    gaps = df["date"].diff().dt.days
    for i in df.index[gaps > GAP_DAYS]:
        info.append(
            f"{symbol}: {int(gaps[i])}-day gap before {df.loc[i, 'date']:%Y-%m-%d}"
        )

    # A big one-day move is a real market event if volume spiked with it; on
    # ordinary volume it looks like an unadjusted split/bonus, which is a failure.
    moves = df["close"].pct_change().abs()
    typical_volume = df["volume"].shift(1).rolling(20, min_periods=5).median()
    for i in df.index[moves > BIG_MOVE]:
        when = f"{df.loc[i, 'date']:%Y-%m-%d}"
        spike = df.loc[i, "volume"] / typical_volume[i] if typical_volume[i] > 0 else 0
        if spike >= VOLUME_SPIKE:
            info.append(
                f"{symbol}: close moved {moves[i]:.1%} on {when} with volume "
                f"{spike:.1f}x normal (a real event, not a data error)"
            )
        else:
            fails.append(
                f"{symbol}: close moved {moves[i]:.1%} in one day on {when} on "
                f"ordinary volume (possible unadjusted split/bonus)"
            )

    ratio = df["adj_close"] / df["close"]
    steps = ratio.pct_change().abs()
    dividend_steps = df.index[steps > RATIO_INFO]
    for i in df.index[steps > RATIO_FAIL]:
        fails.append(
            f"{symbol}: adj_close/close jumped {steps[i]:.1%} on "
            f"{df.loc[i, 'date']:%Y-%m-%d} (too big for a dividend)"
        )
    info.append(
        f"{symbol}: {len(dividend_steps)} dividend-sized adjustment steps, "
        f"largest {steps.max():.2%}"
    )
    return df


def check_resampled(symbol: str, timeframe: str, daily: pd.DataFrame, fails: list) -> None:
    df = load(timeframe, symbol)
    label = f"{symbol} {timeframe}"
    basic_checks(df, label, fails)
    if not df["date"].is_monotonic_increasing:
        return
    if int(df["volume"].sum()) != int(daily["volume"].sum()):
        fails.append(f"{label}: total volume differs from daily")
    if df["open"].iloc[0] != daily["open"].iloc[0]:
        fails.append(f"{label}: first open differs from daily")
    for col in ("close", "adj_close"):
        if df[col].iloc[-1] != daily[col].iloc[-1]:
            fails.append(f"{label}: last {col} differs from daily")
    if df["high"].max() != daily["high"].max() or df["low"].min() != daily["low"].min():
        fails.append(f"{label}: overall high/low differs from daily")


def main() -> int:
    fails: list[str] = []
    info: list[str] = []
    for symbol in TICKERS:
        for tf in ("daily", "weekly", "monthly"):
            if not (ROOT / "data" / tf / f"{symbol}.csv").exists():
                print(f"Missing data/{tf}/{symbol}.csv. Run the download and resample scripts first.")
                return 1
        daily = check_daily(symbol, fails, info)
        for tf in ("weekly", "monthly"):
            check_resampled(symbol, tf, daily, fails)
        print(
            f"{symbol}: {len(daily)} daily rows, "
            f"{daily['date'].iloc[0]:%Y-%m-%d} to {daily['date'].iloc[-1]:%Y-%m-%d}"
        )

    print("\nINFO (for a human to read, not failures):")
    for line in info:
        print(f"  {line}")

    if fails:
        print("\nFAILURES:")
        for line in fails:
            print(f"  {line}")
        return 1
    print("\nAll checks passed for all stocks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
