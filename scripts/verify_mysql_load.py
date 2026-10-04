"""Prove that MySQL holds exactly what the CSV files hold.

For every stock and timeframe: the row counts match and EVERY value matches
(dates, open, high, low, close, adj_close, volume). Also checks that the loader
in app/prices.py returns the same DataFrame from MySQL as from the CSVs, and
that there are no stray rows for unknown stocks.

Run:  python scripts/verify_mysql_load.py
"""
import sys
from pathlib import Path

import pandas as pd
from sqlmodel import Session, func, select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import db, prices  # noqa: E402
from app.models import PriceBar, Stock  # noqa: E402
from app.stocks import TICKERS  # noqa: E402


def main() -> int:
    if not db.is_reachable():
        print("MySQL is not configured or not reachable; nothing to verify.")
        return 1

    fails: list[str] = []
    checked_values = 0
    for symbol in TICKERS:
        for timeframe in prices.TIMEFRAMES:
            label = f"{symbol} {timeframe}"
            csv = prices._from_csv(symbol, timeframe)
            sql = prices._from_database(symbol, timeframe)
            if len(csv) != len(sql):
                fails.append(f"{label}: {len(csv)} CSV rows vs {len(sql)} MySQL rows")
                continue
            try:
                pd.testing.assert_frame_equal(csv, sql, check_exact=True)
            except AssertionError as exc:
                fails.append(f"{label}: values differ: {str(exc).splitlines()[0]}")
                continue
            checked_values += csv.size
            print(f"  OK  {label:<24} {len(csv):>5} rows identical")

    with Session(db.get_engine()) as session:
        total = session.exec(select(func.count()).select_from(PriceBar)).one()
        stocks = session.exec(select(func.count()).select_from(Stock)).one()
        known = session.exec(
            select(func.count()).select_from(PriceBar).where(PriceBar.symbol.in_(list(TICKERS)))
        ).one()
    if stocks != len(TICKERS):
        fails.append(f"stock table has {stocks} rows, expected {len(TICKERS)}")
    if total != known:
        fails.append(f"{total - known} pricebar rows belong to unknown stocks")

    # The app's own loader must hand back the same frame whichever source it uses.
    prices._use_database.cache_clear()
    prices.load_prices.cache_clear()
    via_loader = prices.load_prices("MARUTI.NS", "weekly")
    if not prices._use_database():
        fails.append("app/prices.py did not choose MySQL even though it is reachable")
    pd.testing.assert_frame_equal(via_loader, prices._from_csv("MARUTI.NS", "weekly"), check_exact=True)

    if fails:
        print("\nFAILURES:")
        for line in fails:
            print(f"  {line}")
        return 1
    print(f"\nMySQL matches the CSVs exactly: {total} price rows, {checked_values:,} values compared.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
