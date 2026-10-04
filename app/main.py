import copy
import functools
import logging
import math
from contextlib import asynccontextmanager
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from fastapi.concurrency import run_in_threadpool

from app import ai_context, ai_provider, db, explanations, indicators, prices, rsi_zones
from app.formatting import format_inr
from app.stocks import EXCHANGE, TICKERS
from app.systems import backtest as backtest_engine
from app.models import DEFAULT_USER_ID, CupConfirmation, JournalEntry, WatchlistItem
from app.systems import cup_pattern, portfolio_holdings, trend_following, value_buy

BASE_DIR = Path(__file__).resolve().parent

# Chart settings. The JS reads these from the candles endpoint, so they live here only.
DEFAULT_BARS_VISIBLE = {"daily": 250, "weekly": 156, "monthly": 120}
SMA_PERIOD = 20
RSI_PERIOD = 14
SMA_LABELS = {"daily": "20-day average", "weekly": "20-week average", "monthly": "20-month average"}

logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s: %(message)s")
log = logging.getLogger("investiq")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # One reachability check at startup (a failed connect takes ~4 s on Windows,
    # so never do it twice). prices._use_database() caches and logs the answer.
    if prices._use_database():
        db.init_db()
        log.info("Database ready (tables created if missing)")
    elif db.is_configured():
        log.warning("DATABASE_URL is set but MySQL is not reachable; DB features return 503")
    else:
        log.info("No DATABASE_URL set; DB features return 503, prices come from CSV files")
    yield


app = FastAPI(title="InvestIQ AI", lifespan=lifespan)
templates = Jinja2Templates(directory=BASE_DIR / "templates")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.middleware("http")
async def no_cache_static(request: Request, call_next):
    """Static files are revalidated on every load, so an edited CSS/JS file is never stale."""
    response = await call_next(request)
    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


templates.env.filters["inr"] = format_inr


def absolute_url(request: Request, path: str) -> str:
    """An absolute URL built from the incoming request, never hard-coded. Behind a proxy the
    X-Forwarded-Proto / X-Forwarded-Host headers win, so previews get https when they should."""
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme).split(",")[0].strip()
    host = request.headers.get("x-forwarded-host", request.headers.get("host", request.url.netloc)).split(",")[0].strip()
    return f"{scheme}://{host}{path}"


templates.env.globals["absolute_url"] = absolute_url


# ---------------------------------------------------------------------------
# Errors: JSON (with a readable "detail") for /api/*, a styled page for everything else
# ---------------------------------------------------------------------------
ERROR_PAGES = {
    404: ("Page not found", "There is no page at this address. The app covers five stocks: "
          + ", ".join(TICKERS.values()) + "."),
    405: ("Not allowed", "This address cannot be used that way."),
    500: ("Something went wrong", "The app hit an unexpected problem. Reloading the page usually helps."),
}


def _is_api(request: Request) -> bool:
    return request.url.path.startswith("/api/")


def _error_page(request: Request, status: int, detail: str | None = None):
    heading, message = ERROR_PAGES.get(status, ("Something went wrong", detail or "The request could not be completed."))
    if status == 404 and detail and detail.startswith("Unknown stock"):
        message = f"{detail}. " + ERROR_PAGES[404][1]
    return templates.TemplateResponse(request, "error.html",
                                      {"status": status, "heading": heading, "message": message}, status_code=status)


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    if _is_api(request):
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=getattr(exc, "headers", None))
    return _error_page(request, exc.status_code, str(exc.detail))


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    if _is_api(request):
        # the frontend shows data.detail directly, so it must be a sentence, not a list
        return JSONResponse({"detail": "The request was not in the expected form. Please reload the page and try again."},
                            status_code=422)
    return _error_page(request, 404)


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):
    log.exception("Unexpected error on %s", request.url.path)
    if _is_api(request):
        return JSONResponse({"detail": "Something went wrong on the server. Please try again."}, status_code=500)
    return _error_page(request, 500)


def _require_stock(symbol: str) -> str:
    if symbol not in TICKERS:
        raise HTTPException(status_code=404, detail=f"Unknown stock: {symbol}")
    return TICKERS[symbol]


def _require_timeframe(timeframe: str) -> str:
    if timeframe not in prices.TIMEFRAMES:
        raise HTTPException(status_code=400, detail="timeframe must be daily, weekly or monthly")
    return timeframe


def adjusted_candles(df: pd.DataFrame) -> pd.DataFrame:
    """Chart candles on the ADJUSTED scale.

    Close is adj_close. Open/high/low are scaled by adj_close / close so each
    candle keeps its true shape and agrees with the (adjusted) indicators.
    """
    ratio = df["adj_close"] / df["close"]
    return pd.DataFrame({
        "time": df["date"].dt.strftime("%Y-%m-%d"),
        "open": (df["open"] * ratio).round(2),
        "high": (df["high"] * ratio).round(2),
        "low": (df["low"] * ratio).round(2),
        "close": df["adj_close"].round(2),
    })


def _series_points(times: pd.Series, values: pd.Series) -> list[dict]:
    """[{time, value}] with the not-yet-defined (NaN) leading values left out."""
    keep = values.notna()
    return [
        {"time": t, "value": round(float(v), 2)}
        for t, v in zip(times[keep], values[keep])
    ]


def latest_weekly_reading(symbol: str) -> dict:
    """The newest COMPLETED weekly bar and its readings. Cached; each caller gets its own copy."""
    return dict(_latest_weekly_reading_cached(symbol))


@functools.lru_cache(maxsize=None)
def _latest_weekly_reading_cached(symbol: str) -> dict:
    """The newest COMPLETED weekly bar and its computed readings (all from app/indicators)."""
    df = prices.load_completed_prices(symbol, "weekly")
    close = df["adj_close"]
    sma = indicators.sma(close, SMA_PERIOD)
    rsi = indicators.rsi(close, RSI_PERIOD)
    last_close, last_sma, last_rsi = float(close.iloc[-1]), float(sma.iloc[-1]), float(rsi.iloc[-1])
    week_ago_rsi = float(rsi.iloc[-1 - rsi_zones.BARS_PER_WEEK["weekly"]])
    vs_sma = None if math.isnan(last_sma) else (last_close / last_sma - 1) * 100
    zone = rsi_zones.zone(last_rsi)
    trend = rsi_zones.trend(last_rsi, week_ago_rsi)
    return {
        "zone_note": explanations.rsi_zone_note(zone, last_rsi) if zone else None,
        "trend_note": explanations.rsi_trend_note(trend, last_rsi, None if math.isnan(week_ago_rsi) else week_ago_rsi) if trend else None,
        "week_ending": df["date"].iloc[-1].strftime("%Y-%m-%d"),
        "close": last_close,
        "sma": None if math.isnan(last_sma) else last_sma,
        "vs_sma_pct": vs_sma,
        "rsi": None if math.isnan(last_rsi) else last_rsi,
        "rsi_zone": zone,
        "rsi_trend": trend,
    }


@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(request, "home.html", {"stocks": TICKERS})


@app.get("/stock/{symbol}")
def stock_page(request: Request, symbol: str):
    name = _require_stock(symbol)
    return templates.TemplateResponse(request, "stock.html", {
        "symbol": symbol,
        "name": name,
        "exchange": EXCHANGE,
        "reading": latest_weekly_reading(symbol),
        "sma_period": SMA_PERIOD,
        "default_capital": int(DEFAULT_CAPITAL),
        "ai_configured": ai_provider.is_configured(),
        "ai_not_configured_message": ai_provider.NOT_CONFIGURED_MESSAGE,
    })


@app.get("/api/stocks/{symbol}/system1")
def system1(symbol: str):
    """System 1 (Trend Following). Weekly only: the system is not defined on other timeframes."""
    _require_stock(symbol)
    current = trend_following.current_signal(symbol)
    return {
        "symbol": symbol,
        "timeframe": "weekly",
        "downloaded_on": prices.downloaded_on().isoformat(),
        "current": current,
        "note": explanations.system1_note(current) if current else None,
        "signals": trend_following.signals(symbol),
    }


DEFAULT_CAPITAL = 100000.0


def _parse_capital(capital: str | None) -> float:
    """Capital from the query string, with a plain-English 400 if it is unusable."""
    if capital is None or capital.strip() == "":
        return DEFAULT_CAPITAL
    try:
        value = float(capital.replace(",", ""))
    except ValueError:
        raise HTTPException(status_code=400, detail="Capital must be a number.")
    problem = backtest_engine.validate_capital(value)
    if problem:
        raise HTTPException(status_code=400, detail=problem)
    return value


@app.get("/api/stocks/{symbol}/backtest")
def stock_backtest(symbol: str, capital: str | None = None):
    """System 1 backtest for one stock. All money is hypothetical."""
    _require_stock(symbol)
    result = trend_following.backtest(symbol, _parse_capital(capital))
    return {"symbol": symbol, "system": "trend_following",
            "note": explanations.backtest_note(result["summary"]), **result}


@app.get("/api/stocks/{symbol}/value-buy")
def value_buy_endpoint(symbol: str, capital: str | None = None):
    """System 3 (Value Buy): current reading + backtest. All backtest money is hypothetical."""
    _require_stock(symbol)
    amount = _parse_capital(capital)
    current = value_buy.current_signal(symbol)
    result = value_buy.backtest(symbol, amount)
    return {
        "symbol": symbol,
        "system": "value_buy",
        "current": current,
        "note": explanations.value_buy_note(current),
        "backtest": {**result, "note": explanations.backtest_note(result["summary"])},
    }


MAX_QUESTION_CHARS = 1000
MAX_HISTORY_TURNS = 20
MAX_TURN_CHARS = 4000


@app.post("/api/stocks/{symbol}/ask")
async def ask_ai(symbol: str, request: Request):
    """Chat about one stock. ALWAYS HTTP 200: {"reply": text, "error": null} or {"reply": null, "error": text}.

    Stateless: the browser sends the whole conversation each time; nothing is stored.
    """
    def fail(message: str) -> dict:
        return {"reply": None, "error": message}

    if symbol not in TICKERS:
        return fail("This stock is not one of the five the app covers.")
    try:
        body = await request.json()
    except Exception:
        return fail("The question could not be read. Please try again.")
    if not isinstance(body, dict):
        return fail("The question could not be read. Please try again.")
    question = body.get("question")
    history = body.get("history") or []
    if not isinstance(question, str) or not question.strip():
        return fail("Please type a question first.")
    if len(question) > MAX_QUESTION_CHARS:
        return fail(f"Please keep the question under {MAX_QUESTION_CHARS} characters.")
    if not isinstance(history, list):
        return fail("The conversation could not be read. Please reload the page.")
    turns = []
    for t in history[-MAX_HISTORY_TURNS:]:
        if isinstance(t, dict) and t.get("role") in ("user", "ai") and isinstance(t.get("text"), str) and t["text"].strip():
            turns.append({"role": t["role"], "text": t["text"][:MAX_TURN_CHARS]})
    turns.append({"role": "user", "text": question.strip()})
    if not ai_provider.is_configured():
        return fail(ai_provider.NOT_CONFIGURED_MESSAGE)
    try:
        reply = await run_in_threadpool(ai_provider.ask, ai_context.system_prompt(symbol), turns)
    except ai_provider.AIUnavailableError as exc:
        return fail(str(exc))
    return {"reply": reply, "error": None}


# ---------------------------------------------------------------------------
# Watchlist, journal, holdings (MySQL; HTTP 503 with a plain message when unavailable)
# ---------------------------------------------------------------------------
def current_states(symbol: str) -> dict:
    """Both systems' current state for one stock, reusing the existing computation.
    Cached (prices never change while the app runs); each caller gets its own copy."""
    return copy.deepcopy(_current_states_cached(symbol))


@functools.lru_cache(maxsize=None)
def _current_states_cached(symbol: str) -> dict:
    s1 = trend_following.current_signal(symbol)
    vb = value_buy.current_signal(symbol)
    return {
        "week_ending": s1["week_ending"] if s1 else vb["week_ending"],
        "system1": {"state": s1["state"], "developing": s1["developing"]} if s1 else None,
        "value_buy": {"state": vb["state"], "exit_reason": vb["exit_reason"]},
    }


def latest_prices() -> dict:
    """Latest completed weekly close per stock, with its date (a one-time download, never live)."""
    out = {}
    for symbol in TICKERS:
        w = prices.load_completed_prices(symbol, "weekly")
        out[symbol] = {"price": round(float(w["close"].iloc[-1]), 2), "as_of": w["date"].iloc[-1].strftime("%Y-%m-%d")}
    return out


def _watch_row(item: WatchlistItem) -> dict:
    return {"symbol": item.symbol, "name": TICKERS.get(item.symbol, item.symbol),
            "added_at": item.added_at.isoformat(timespec="seconds"), **current_states(item.symbol)}


@app.get("/api/watchlist")
def watchlist_list(session: Session = Depends(db.get_session)):
    items = session.exec(select(WatchlistItem).where(WatchlistItem.user_id == DEFAULT_USER_ID)
                         .order_by(WatchlistItem.added_at)).all()
    return {"items": [_watch_row(i) for i in items if i.symbol in TICKERS]}


@app.post("/api/watchlist")
async def watchlist_add(request: Request, session: Session = Depends(db.get_session)):
    body = await _json_body(request)
    symbol = body.get("symbol")
    if symbol not in TICKERS:
        raise HTTPException(status_code=400, detail="Choose one of the five stocks the app covers.")
    existing = session.exec(select(WatchlistItem).where(WatchlistItem.user_id == DEFAULT_USER_ID,
                                                        WatchlistItem.symbol == symbol)).first()
    if existing:
        return {"item": _watch_row(existing), "created": False}
    item = WatchlistItem(user_id=DEFAULT_USER_ID, symbol=symbol)
    session.add(item)
    session.commit()
    session.refresh(item)
    return {"item": _watch_row(item), "created": True}


@app.delete("/api/watchlist/{symbol}")
def watchlist_remove(symbol: str, session: Session = Depends(db.get_session)):
    item = session.exec(select(WatchlistItem).where(WatchlistItem.user_id == DEFAULT_USER_ID,
                                                    WatchlistItem.symbol == symbol)).first()
    if not item:
        raise HTTPException(status_code=404, detail="That stock is not on your watchlist.")
    session.delete(item)
    session.commit()
    return {"removed": symbol}


async def _json_body(request: Request) -> dict:
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="The request could not be read.")
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="The request could not be read.")
    return body


def _validate_journal(body: dict) -> dict:
    """Server-side validation of a journal entry. Raises 400 with a plain-English message."""
    symbol = body.get("symbol")
    if symbol not in TICKERS:
        raise HTTPException(status_code=400, detail="Choose one of the five stocks the app covers.")
    side = str(body.get("side", "")).upper()
    if side not in ("BUY", "SELL"):
        raise HTTPException(status_code=400, detail="Side must be BUY or SELL.")
    qty = body.get("quantity")
    if isinstance(qty, str) and qty.strip().isdigit():
        qty = int(qty.strip())
    if isinstance(qty, bool) or not isinstance(qty, int) or qty <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be a whole number of shares, more than zero.")
    if qty > 10_000_000:
        raise HTTPException(status_code=400, detail="Quantity is too large to be a real trade.")
    raw_price = body.get("price")
    try:
        price = Decimal(str(raw_price).replace(",", "").strip())
    except (InvalidOperation, ValueError):
        raise HTTPException(status_code=400, detail="Price must be a number.")
    if not price.is_finite() or price <= 0:
        raise HTTPException(status_code=400, detail="Price must be more than zero.")
    if price.as_tuple().exponent < -2:
        raise HTTPException(status_code=400, detail="Price can have at most two decimal places (paise).")
    if price >= Decimal("10000000000"):
        raise HTTPException(status_code=400, detail="Price is too large to be a real trade.")
    try:
        trade_date = date.fromisoformat(str(body.get("trade_date", "")))
    except ValueError:
        raise HTTPException(status_code=400, detail="Trade date must be a real date (YYYY-MM-DD).")
    if trade_date > date.today():
        raise HTTPException(status_code=400, detail="Trade date cannot be in the future.")
    if trade_date < date(1990, 1, 1):
        raise HTTPException(status_code=400, detail="Trade date is too far in the past.")
    notes = body.get("notes")
    if notes is not None and not isinstance(notes, str):
        raise HTTPException(status_code=400, detail="Notes must be text.")
    notes = (notes or "").strip() or None
    if notes and len(notes) > 1000:
        raise HTTPException(status_code=400, detail="Notes can be at most 1,000 characters.")
    return {"symbol": symbol, "side": side, "quantity": qty, "price": price, "trade_date": trade_date, "notes": notes}


def _journal_row(e: JournalEntry) -> dict:
    return {"id": e.id, "symbol": e.symbol, "name": TICKERS.get(e.symbol, e.symbol), "side": e.side,
            "quantity": e.quantity, "price": float(e.price), "trade_date": e.trade_date.isoformat(),
            "notes": e.notes, "created_at": e.created_at.isoformat(timespec="seconds")}


def _journal_entries(session: Session) -> list[JournalEntry]:
    return session.exec(select(JournalEntry).where(JournalEntry.user_id == DEFAULT_USER_ID)
                        .order_by(JournalEntry.trade_date.desc(), JournalEntry.id.desc())).all()


@app.get("/api/journal")
def journal_list(session: Session = Depends(db.get_session)):
    return {"entries": [_journal_row(e) for e in _journal_entries(session)]}


@app.post("/api/journal")
async def journal_add(request: Request, session: Session = Depends(db.get_session)):
    fields = _validate_journal(await _json_body(request))
    entry = JournalEntry(user_id=DEFAULT_USER_ID, **fields)
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return {"entry": _journal_row(entry)}


@app.delete("/api/journal/{entry_id}")
def journal_delete(entry_id: int, session: Session = Depends(db.get_session)):
    entry = session.get(JournalEntry, entry_id)
    if not entry or entry.user_id != DEFAULT_USER_ID:
        raise HTTPException(status_code=404, detail="That journal entry does not exist.")
    session.delete(entry)
    session.commit()
    return {"deleted": entry_id}


@app.get("/api/journal/holdings")
def journal_holdings(session: Session = Depends(db.get_session)):
    entries = [{"id": e.id, "symbol": e.symbol, "side": e.side, "quantity": e.quantity,
                "price": float(e.price), "trade_date": e.trade_date.isoformat()} for e in _journal_entries(session)]
    result = portfolio_holdings.compute_holdings(entries, latest_prices(), TICKERS)
    return {**result, "prices_as_of": next(iter(latest_prices().values()))["as_of"],
            "downloaded_on": prices.downloaded_on().isoformat()}


# ---------------------------------------------------------------------------
# Screener and home page
# ---------------------------------------------------------------------------
def screener_row(symbol: str) -> dict:
    """One stock's current readings, reusing existing computation only (nothing new is calculated)."""
    reading = latest_weekly_reading(symbol)
    return {
        "symbol": symbol,
        "name": TICKERS[symbol],
        "close": round(reading["close"], 2),
        "rsi": None if reading["rsi"] is None else round(reading["rsi"], 2),
        "rsi_zone": reading["rsi_zone"],
        "rsi_trend": reading["rsi_trend"],
        **current_states(symbol),
    }


@app.get("/api/screener")
def screener_api():
    return {"rows": [screener_row(s) for s in TICKERS], "downloaded_on": prices.downloaded_on().isoformat()}


FILTER_OPTIONS = {
    "rsi_zone": list(rsi_zones.ZONES),
    "rsi_trend": list(rsi_zones.TRENDS),
    "system1": list(trend_following.STATES) + ["DEVELOPING"],
    "value_buy": list(value_buy.STATES),
}


@app.get("/screener")
def screener_page(request: Request):
    return templates.TemplateResponse(request, "screener.html", {"filters": FILTER_OPTIONS})


@app.get("/watchlist")
def watchlist_page(request: Request):
    return templates.TemplateResponse(request, "watchlist.html", {"stocks": TICKERS})


@app.get("/journal")
def journal_page(request: Request):
    return templates.TemplateResponse(request, "journal.html", {"stocks": TICKERS, "today": date.today().isoformat()})


# ---------------------------------------------------------------------------
# System 2: Cup & Handle
# ---------------------------------------------------------------------------
def _cup_confirmed(symbol: str, left_rim_date: str) -> bool | None:
    """True/False from MySQL, or None when the database is not available (the GET still works)."""
    if not db.is_configured():
        return None
    try:
        with Session(db.get_engine()) as session:
            row = session.exec(select(CupConfirmation).where(
                CupConfirmation.user_id == DEFAULT_USER_ID, CupConfirmation.symbol == symbol,
                CupConfirmation.left_rim_date == date.fromisoformat(left_rim_date))).first()
            return row is not None
    except SQLAlchemyError:
        return None


@app.get("/api/stocks/{symbol}/cup-pattern")
def cup_pattern_endpoint(symbol: str, capital: str | None = None):
    """Cup & Handle: detection status (a POSSIBLE formation only), confirmation status, and one
    backtest per selling ladder. Buy point / entry / stop / ladder levels are included ONLY
    after a human has confirmed the cup. All backtest money is hypothetical."""
    _require_stock(symbol)
    amount = _parse_capital(capital)
    ev = cup_pattern.evaluate(symbol)
    status = cup_pattern.current_status(symbol, ev)
    confirmed = None
    if status["status"] == "POSSIBLE":
        confirmed = _cup_confirmed(symbol, status["cup"]["left_rim_date"])
    levels = status.pop("levels", None)
    backtests = cup_pattern.backtest(symbol, amount, ev)
    for result in backtests.values():
        result["note"] = explanations.backtest_note(result["summary"], unit="months")
    note_status = {**status, "levels": levels} if levels else status
    return {
        "symbol": symbol,
        "system": "cup_pattern",
        **status,
        "confirmed": confirmed,
        # can a confirmation be read and saved right now?
        "db_available": (confirmed is not None) if status["status"] == "POSSIBLE" else db.is_configured(),
        "levels": levels if confirmed else None,
        "note": explanations.cup_note(note_status, bool(confirmed)),
        "modes": [{"key": m, "label": cup_pattern.MODE_LABELS[m]} for m in cup_pattern.MODES],
        "backtests": backtests,
    }


@app.post("/api/stocks/{symbol}/cup-pattern/confirm")
def cup_pattern_confirm(symbol: str, session: Session = Depends(db.get_session)):
    """A human confirms the CURRENT possible cup. Takes no request body: the cup is recomputed
    here, so nothing the browser sends can change what gets confirmed."""
    _require_stock(symbol)
    status = cup_pattern.current_status(symbol)
    if status["status"] != "POSSIBLE":
        raise HTTPException(status_code=409, detail="There is no possible cup formation to confirm for this stock.")
    rim = date.fromisoformat(status["cup"]["left_rim_date"])
    existing = session.exec(select(CupConfirmation).where(
        CupConfirmation.user_id == DEFAULT_USER_ID, CupConfirmation.symbol == symbol,
        CupConfirmation.left_rim_date == rim)).first()
    if not existing:
        session.add(CupConfirmation(user_id=DEFAULT_USER_ID, symbol=symbol, left_rim_date=rim))
        session.commit()
    return {"confirmed": True, "created": existing is None, "left_rim_date": rim.isoformat(), "levels": status["levels"]}


@app.get("/api/portfolio/backtest")
def portfolio_backtest(capital: str | None = None):
    """System 1 across all five stocks, capital split equally. All money is hypothetical."""
    result = trend_following.portfolio_backtest(_parse_capital(capital))
    return {"system": "trend_following",
            "note": explanations.backtest_note(result["summary"], portfolio=True), **result}


@app.get("/portfolio")
def portfolio_page(request: Request):
    return templates.TemplateResponse(request, "portfolio.html", {"default_capital": int(DEFAULT_CAPITAL)})


@app.get("/api/stocks/{symbol}/candles")
def candles(symbol: str, timeframe: str = "weekly"):
    _require_stock(symbol)
    _require_timeframe(timeframe)
    df = prices.load_prices(symbol, timeframe)
    close = df["adj_close"]
    sma = indicators.sma(close, SMA_PERIOD)
    rsi = indicators.rsi(close, RSI_PERIOD)
    candle_frame = adjusted_candles(df)
    times = candle_frame["time"]
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "default_bars_visible": DEFAULT_BARS_VISIBLE[timeframe],
        "sma_label": SMA_LABELS[timeframe],
        "rsi_period": RSI_PERIOD,
        "rsi_zone_bounds": [rsi_zones.BEARISH_BELOW, rsi_zones.BULLISH_ABOVE],
        "candles": candle_frame.to_dict("records"),
        "sma": _series_points(times, sma),
        "rsi": _series_points(times, rsi),
    }
