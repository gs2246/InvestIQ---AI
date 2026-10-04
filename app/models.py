"""All database tables (SQLModel), for MySQL.

Conventions:
- Every string column that is indexed or part of a unique key has an explicit
  max_length, because MySQL cannot index an unbounded VARCHAR.
- Prices are DECIMAL(12,2); app/prices.py converts them to float for pandas.
- Every user-owned table has a real user_id, all set to DEFAULT_USER_ID for now
  (there is no login screen). Adding accounts later is a data migration.
- journal rows are REAL trades the user made, never hypothetical backtest trades.
"""
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, Column, Index, Numeric, UniqueConstraint
from sqlmodel import Field, SQLModel

DEFAULT_USER_ID = "default"


def _utcnow() -> datetime:
    # Timezone-aware UTC. SQLModel's UTCDateTime type requires an aware value, writes it
    # to MySQL's DATETIME as UTC, and re-attaches UTC when reading it back.
    return datetime.now(timezone.utc)


def _price() -> Column:
    return Column(Numeric(12, 2), nullable=False)


class Stock(SQLModel, table=True):
    symbol: str = Field(primary_key=True, max_length=20)
    name: str = Field(max_length=100)
    exchange: str = Field(max_length=10)


class PriceBar(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("symbol", "timeframe", "date", name="uq_pricebar_symbol_tf_date"),
        Index("ix_pricebar_symbol_tf", "symbol", "timeframe"),
    )

    id: int | None = Field(default=None, primary_key=True)
    symbol: str = Field(foreign_key="stock.symbol", max_length=20)
    timeframe: str = Field(max_length=10)  # daily / weekly / monthly
    date: date
    open: Decimal = Field(sa_column=_price())
    high: Decimal = Field(sa_column=_price())
    low: Decimal = Field(sa_column=_price())
    close: Decimal = Field(sa_column=_price())
    adj_close: Decimal = Field(sa_column=_price())
    volume: int = Field(sa_column=Column(BigInteger, nullable=False))


class WatchlistItem(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("user_id", "symbol", name="uq_watchlist_user_symbol"),)

    id: int | None = Field(default=None, primary_key=True)
    user_id: str = Field(default=DEFAULT_USER_ID, max_length=40)
    symbol: str = Field(max_length=20)
    added_at: datetime = Field(default_factory=_utcnow)


class JournalEntry(SQLModel, table=True):
    __table_args__ = (
        CheckConstraint("side IN ('BUY', 'SELL')", name="ck_journal_side"),
        CheckConstraint("quantity > 0", name="ck_journal_quantity_positive"),
        CheckConstraint("price > 0", name="ck_journal_price_positive"),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: str = Field(default=DEFAULT_USER_ID, max_length=40, index=True)
    symbol: str = Field(max_length=20)
    side: str = Field(max_length=4)  # BUY / SELL
    quantity: int
    price: Decimal = Field(sa_column=_price())
    trade_date: date
    notes: str | None = Field(default=None, max_length=1000)
    created_at: datetime = Field(default_factory=_utcnow)


class CupConfirmation(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("user_id", "symbol", "left_rim_date", name="uq_cup_user_symbol_rim"),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: str = Field(default=DEFAULT_USER_ID, max_length=40)
    symbol: str = Field(max_length=20)
    left_rim_date: date
    confirmed_at: datetime = Field(default_factory=_utcnow)
