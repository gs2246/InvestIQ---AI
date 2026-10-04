"""Create the MySQL tables and load every price CSV into them.

Idempotent: safe to run as many times as you like. For each stock/timeframe the
old rows are deleted and the CSV rows inserted inside ONE transaction, so a
failure part-way leaves the previous data untouched, and running twice never
creates duplicates. The watchlist, journal and cup tables are never touched.

Needs DATABASE_URL in .env and MySQL running.

Run:  python scripts/setup_db.py
"""
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import delete, insert
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import db  # noqa: E402
from app.models import PriceBar, Stock  # noqa: E402
from app.stocks import EXCHANGE, TICKERS  # noqa: E402

TIMEFRAMES = ("daily", "weekly", "monthly")
BATCH = 2000


def main() -> int:
    if not db.is_configured():
        print("DATABASE_URL is not set. Copy .env.example to .env and fill it in first.")
        return 1
    if not db.is_reachable():
        print(
            "Could not connect to MySQL. Check that the MySQL80 service is running and\n"
            "that the user, password and database in DATABASE_URL (.env) are correct."
        )
        return 1

    db.init_db()
    print("Tables ready: stock, pricebar, watchlistitem, journalentry, cupconfirmation")

    try:
        with Session(db.get_engine()) as session:
            for symbol, name in TICKERS.items():
                session.merge(Stock(symbol=symbol, name=name, exchange=EXCHANGE))
            session.flush()

            for symbol in TICKERS:
                for timeframe in TIMEFRAMES:
                    df = pd.read_csv(ROOT / "data" / timeframe / f"{symbol}.csv")
                    df["date"] = pd.to_datetime(df["date"]).dt.date
                    df.insert(0, "timeframe", timeframe)
                    df.insert(0, "symbol", symbol)
                    session.exec(
                        delete(PriceBar).where(
                            PriceBar.symbol == symbol, PriceBar.timeframe == timeframe
                        )
                    )
                    records = df.to_dict("records")
                    for i in range(0, len(records), BATCH):
                        session.exec(insert(PriceBar), params=records[i : i + BATCH])
                    print(f"  {symbol:<14} {timeframe:<8} {len(records):>5} rows")
            session.commit()  # everything or nothing
    except SQLAlchemyError as exc:
        print(f"\nLoad failed and was rolled back (the database is unchanged): {exc}")
        return 1

    print("\nDone. Next: python scripts/verify_mysql_load.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
