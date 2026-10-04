"""One-time download of daily OHLCV from Yahoo Finance.

This is the ONLY place in the project that talks to Yahoo. The running site
never does, so it cannot break when Yahoo is down.

Writes, per stock:
  data/raw/<symbol>.csv    exactly what Yahoo returned (untouched)
  data/daily/<symbol>.csv  cleaned: snake_case columns, ascending dates,
                           prices rounded to 2 decimals

Both `close` (split-adjusted) and `adj_close` (also dividend-adjusted) are kept.
All indicators and backtests use adj_close.

Run:  python scripts/download_data.py
"""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.stocks import TICKERS  # noqa: E402

START = "2011-01-03"
PRICE_COLS = ["open", "high", "low", "close", "adj_close"]


def clean(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    df.index = pd.to_datetime(df.index)
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    df.index.name = "date"
    df = df.reset_index()
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    df = df[["date"] + PRICE_COLS + ["volume"]]
    df = df.sort_values("date").reset_index(drop=True)
    df["date"] = df["date"].dt.strftime("%Y-%m-%d")
    df[PRICE_COLS] = df[PRICE_COLS].round(2)
    return df


def main() -> int:
    raw_dir = ROOT / "data" / "raw"
    daily_dir = ROOT / "data" / "daily"
    raw_dir.mkdir(parents=True, exist_ok=True)
    daily_dir.mkdir(parents=True, exist_ok=True)

    # Yahoo's `end` date is exclusive, so ask for tomorrow to include today.
    end = (date.today() + timedelta(days=1)).isoformat()

    failed = []
    for symbol in TICKERS:
        print(f"Downloading {symbol} ...", end=" ", flush=True)
        raw = yf.download(
            symbol,
            start=START,
            end=end,
            interval="1d",
            auto_adjust=False,  # keep both Close and Adj Close
            multi_level_index=False,
            progress=False,
        )
        if raw is None or raw.empty:
            print("FAILED (no data returned)")
            failed.append(symbol)
            continue
        raw.to_csv(raw_dir / f"{symbol}.csv")
        df = clean(raw)
        df.to_csv(daily_dir / f"{symbol}.csv", index=False)
        print(f"{len(df)} rows, {df['date'].iloc[0]} to {df['date'].iloc[-1]}")

    if failed:
        print(f"\nFailed: {', '.join(failed)}. Nothing was lost; just run the script again.")
        return 1

    # The app needs to know which weekly/monthly bars were still in progress
    # when this data was fetched (see app/prices.py, completed bars).
    meta = {
        "downloaded_on": date.today().isoformat(),
        "note": "Date the one-time Yahoo download ran. A weekly or monthly bar is complete "
                "only if its label date is before this date. Written by scripts/download_data.py.",
    }
    (ROOT / "data" / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print("\nDone. Next: python scripts/resample_data.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
