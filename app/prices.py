"""The one place prices are read from. No other file reads prices directly.

Source: MySQL (PriceBar) if the database is configured and reachable and holds
data for the requested stock; otherwise the committed CSVs in data/<timeframe>/.
Both sources return an identical DataFrame, so callers never care which is used.

Returned columns: date (datetime64), open, high, low, close, adj_close (float),
volume (int), ascending by date. Prices are ADJUSTED-aware: adj_close is what
indicators and backtests use; close/open/high/low are kept for chart scaling.

Results are cached with lru_cache because prices never change at runtime.
CALLERS MUST NEVER MUTATE THE RETURNED DATAFRAME: build new frames from its
columns instead. (The same object is handed to every caller.)
"""
import functools
import json
import logging
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from sqlmodel import Session, select

from app import db
from app.models import PriceBar
from app.stocks import TICKERS

ROOT = Path(__file__).resolve().parents[1]
TIMEFRAMES = ("daily", "weekly", "monthly")
COLUMNS = ["date", "open", "high", "low", "close", "adj_close", "volume"]
PRICE_COLUMNS = ["open", "high", "low", "close", "adj_close"]

log = logging.getLogger("investiq.prices")


@functools.lru_cache(maxsize=1)
def _use_database() -> bool:
    """Decide once per process which source to use, and log it once."""
    if not db.is_configured():
        log.info("Price source: CSV files (DATABASE_URL is not set)")
        return False
    if not db.is_reachable():
        log.warning("Price source: CSV files (MySQL is configured but not reachable)")
        return False
    log.info("Price source: MySQL")
    return True


def _from_csv(symbol: str, timeframe: str) -> pd.DataFrame:
    df = pd.read_csv(ROOT / "data" / timeframe / f"{symbol}.csv", parse_dates=["date"])
    return _normalise(df)


def _from_database(symbol: str, timeframe: str) -> pd.DataFrame:
    stmt = (
        select(
            PriceBar.date, PriceBar.open, PriceBar.high, PriceBar.low,
            PriceBar.close, PriceBar.adj_close, PriceBar.volume,
        )
        .where(PriceBar.symbol == symbol, PriceBar.timeframe == timeframe)
        .order_by(PriceBar.date)
    )
    with Session(db.get_engine()) as session:
        rows = session.exec(stmt).all()
    df = pd.DataFrame(rows, columns=COLUMNS)
    df["date"] = pd.to_datetime(df["date"])
    return _normalise(df)


def _normalise(df: pd.DataFrame) -> pd.DataFrame:
    df = df[COLUMNS].copy()
    # pandas 3 infers different datetime units per source (CSV: us, MySQL: s);
    # pin one so both sources are byte-for-byte the same kind of frame.
    df["date"] = df["date"].astype("datetime64[us]")
    df[PRICE_COLUMNS] = df[PRICE_COLUMNS].astype("float64")  # MySQL gives Decimal
    df["volume"] = df["volume"].astype("int64")
    return df.sort_values("date").reset_index(drop=True)


def adjusted_ohlc(df: pd.DataFrame) -> pd.DataFrame:
    """A NEW frame of open/high/low/close on the adjusted scale (close = adj_close).
    Open/high/low are scaled by adj_close / close, exactly as the chart does."""
    ratio = df["adj_close"] / df["close"]
    return pd.DataFrame({
        "date": df["date"],
        "open": df["open"] * ratio,
        "high": df["high"] * ratio,
        "low": df["low"] * ratio,
        "close": df["adj_close"],
    })


@functools.lru_cache(maxsize=1)
def downloaded_on() -> date:
    """The day the one-time download ran (data/meta.json, written by download_data.py).

    If the file is missing, fall back to the day after the newest daily bar, which
    is the most cautious guess that still treats finished periods as complete.
    """
    try:
        meta = json.loads((ROOT / "data" / "meta.json").read_text(encoding="utf-8"))
        return date.fromisoformat(meta["downloaded_on"])
    except (OSError, ValueError, KeyError):
        newest = load_prices(next(iter(TICKERS)), "daily")["date"].iloc[-1].date()
        log.warning("data/meta.json is missing or unreadable; assuming the download ran the day after %s", newest)
        return newest + timedelta(days=1)


@functools.lru_cache(maxsize=None)
def load_completed_prices(symbol: str, timeframe: str) -> pd.DataFrame:
    """Like load_prices, but only bars that were COMPLETE when the data was downloaded.

    A bar is complete if its label date (the trading day, the week-ending Friday or
    the month-end) is strictly before the download date. Anything that reports a
    signal must use this, so an in-progress week or month is never shown as finished.
    Same no-mutation rule as load_prices.
    """
    df = load_prices(symbol, timeframe)
    return df[df["date"].dt.date < downloaded_on()].reset_index(drop=True)


@functools.lru_cache(maxsize=None)
def load_prices(symbol: str, timeframe: str) -> pd.DataFrame:
    if symbol not in TICKERS:
        raise ValueError(f"Unknown symbol: {symbol}")
    if timeframe not in TIMEFRAMES:
        raise ValueError(f"Unknown timeframe: {timeframe}")
    if _use_database():
        df = _from_database(symbol, timeframe)
        if not df.empty:
            return df
        log.warning("MySQL has no %s %s rows (run scripts/setup_db.py); using CSV", symbol, timeframe)
    return _from_csv(symbol, timeframe)
