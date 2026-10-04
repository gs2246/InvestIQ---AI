"""Derive weekly and monthly candles from the daily CSVs.

Daily is the single source of truth: Yahoo is never queried a second time.

  weekly   calendar week ending Friday   -> data/weekly/<symbol>.csv
  monthly  calendar month end            -> data/monthly/<symbol>.csv

Candle rules: open = first open, high = max high, low = min low,
close = last close, adj_close = last adj_close, volume = sum.
The candle's date is the period label (the Friday / the last calendar day of
the month), not necessarily a day the market was open.

Run:  python scripts/resample_data.py
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.stocks import TICKERS  # noqa: E402

RULES = {"weekly": "W-FRI", "monthly": "ME"}
AGG = {
    "open": "first",
    "high": "max",
    "low": "min",
    "close": "last",
    "adj_close": "last",
    "volume": "sum",
}


def resample(daily: pd.DataFrame, rule: str) -> pd.DataFrame:
    df = daily.copy()
    df["date"] = pd.to_datetime(df["date"])
    out = df.set_index("date").resample(rule, label="right", closed="right").agg(AGG)
    out = out.dropna(subset=["open"])  # weeks/months with no trading at all
    out = out.reset_index()
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    return out


def main() -> int:
    for timeframe in RULES:
        (ROOT / "data" / timeframe).mkdir(parents=True, exist_ok=True)

    for symbol in TICKERS:
        path = ROOT / "data" / "daily" / f"{symbol}.csv"
        if not path.exists():
            print(f"Missing {path}. Run scripts/download_data.py first.")
            return 1
        daily = pd.read_csv(path)
        parts = []
        for timeframe, rule in RULES.items():
            out = resample(daily, rule)
            out.to_csv(ROOT / "data" / timeframe / f"{symbol}.csv", index=False)
            parts.append(f"{len(out)} {timeframe}")
        print(f"{symbol}: {len(daily)} daily -> {', '.join(parts)}")
    print("\nDone. Next: python scripts/verify_data.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
