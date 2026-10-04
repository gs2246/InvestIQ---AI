"""MySQL connection, with graceful degradation.

The app must keep working with no DATABASE_URL, or with MySQL switched off:
charts, signals, backtests and the screener fall back to the committed CSVs
(see app/prices.py). Only watchlist, journal, holdings and cup confirmation
need the database, and they answer HTTP 503 with a plain message.

Mirrors app/ai_provider.py: an is_configured() check plus clear failures.
"""
import logging
import os
from collections.abc import Iterator
from pathlib import Path

from dotenv import load_dotenv
from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine, text

from app import models  # noqa: F401  (importing registers the tables on SQLModel.metadata)

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

log = logging.getLogger("investiq.db")

NOT_CONFIGURED_MESSAGE = (
    "The database isn't configured, so this feature is unavailable. "
    "Set DATABASE_URL in the .env file and make sure MySQL is running."
)

_engine: Engine | None = None


def database_url() -> str:
    return os.environ.get("DATABASE_URL", "").strip()


def is_configured() -> bool:
    """True if a DATABASE_URL is set. Does not check that MySQL is actually up."""
    return bool(database_url())


def get_engine() -> Engine:
    global _engine
    if not is_configured():
        raise RuntimeError("DATABASE_URL is not set")
    if _engine is None:
        # pool_pre_ping: transparently reconnect if MySQL was restarted.
        _engine = create_engine(database_url(), pool_pre_ping=True, pool_recycle=3600)
    return _engine


def is_reachable() -> bool:
    """True if configured AND a trivial query succeeds right now."""
    if not is_configured():
        return False
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError as exc:
        log.warning("MySQL is configured but not reachable: %s", exc.__class__.__name__)
        return False


def init_db() -> None:
    """Create any missing tables. Safe to call repeatedly."""
    SQLModel.metadata.create_all(get_engine())


def get_session() -> Iterator[Session]:
    """FastAPI dependency for routes that need the database.

    Raises HTTP 503 (not a 500 crash) when the database is missing or down.
    """
    if not is_configured():
        raise HTTPException(status_code=503, detail=NOT_CONFIGURED_MESSAGE)
    session = Session(get_engine())
    try:
        session.connection()  # force a real connection now, so failure is caught here
    except SQLAlchemyError:
        session.close()
        raise HTTPException(status_code=503, detail=NOT_CONFIGURED_MESSAGE)
    try:
        yield session
    finally:
        session.close()
