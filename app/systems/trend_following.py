"""System 1: Trend Following. Rules from the user's own notes (BUILD.md section 10).

Evaluated on COMPLETED weekly candles only, using the 20-period SMA of weekly
adjusted closes and RSI(14). ("20 DMA" in the notes means 20 weekly periods,
simple, not exponential.)

    Entry (BUY), only when flat:
        RSI CROSSES from <= 60 to > 60   (prev_rsi <= 60 and rsi > 60, a crossover,
        not a level test)  AND  weekly close > 20-SMA.
    Exit (SELL), only when in a position:
        weekly close < 20-SMA. This is both the exit and the trailing stop. There
        is no fixed stop and no target, and RSI plays no part in the exit.

States, one per completed weekly bar:
    BUY      flat, entry conditions met
    HOLD     in a position, close >= SMA
    SELL     in a position, close < SMA
    NEUTRAL  flat, no trigger

DEVELOPING is a flag on NEUTRAL (not a fifth state): close > SMA, RSI between 50
and 60 and rising.

Deliberate asymmetry: entry needs close STRICTLY above the SMA, holding needs
close at or above it.

Boundary choices (the notes don't say which side an exact value falls on):
    - "between 50 and 60" is inclusive of both 50 and 60;
    - "rising" means RSI is strictly higher than the previous week's RSI.

Bars before the SMA and RSI both exist (the warm-up) have state None: there is
nothing to evaluate, and calling them NEUTRAL would claim a reading we don't have.

The walk is stateful (BUY vs HOLD depends on whether a position is open), so it
is a loop, not a vectorised calculation.
"""
import math

import pandas as pd

from app import indicators, prices
from app.stocks import TICKERS
from app.systems import backtest as bt

SMA_PERIOD = 20
RSI_PERIOD = 14
RSI_LEVEL = 60.0           # the crossover level for entry
DEVELOPING_LOW = 50.0
DEVELOPING_HIGH = 60.0

STATES = ("BUY", "HOLD", "SELL", "NEUTRAL")


def _nan(x: float) -> bool:
    return x is None or (isinstance(x, float) and math.isnan(x))


def run_state_machine(close, sma, rsi) -> tuple[list, list]:
    """Walk the bars in order. Returns (states, developing), one entry per bar.

    `close`, `sma`, `rsi` are equal-length sequences of floats (NaN where not yet
    defined). Kept separate from any DataFrame so it can be tested with
    hand-built numbers.
    """
    states: list = []
    developing: list = []
    in_position = False
    prev_rsi = float("nan")

    for c, s, r in zip(close, sma, rsi):
        if _nan(c) or _nan(s) or _nan(r):
            states.append(None)
            developing.append(False)
            prev_rsi = r
            continue

        if in_position:
            if c < s:
                states.append("SELL")
                in_position = False
            else:
                states.append("HOLD")
            developing.append(False)
        else:
            crossed_up = (not _nan(prev_rsi)) and prev_rsi <= RSI_LEVEL and r > RSI_LEVEL
            if crossed_up and c > s:
                states.append("BUY")
                in_position = True
                developing.append(False)
            else:
                states.append("NEUTRAL")
                developing.append(
                    c > s
                    and DEVELOPING_LOW <= r <= DEVELOPING_HIGH
                    and (not _nan(prev_rsi))
                    and r > prev_rsi
                )
        prev_rsi = r

    return states, developing


def evaluate(symbol: str) -> pd.DataFrame:
    """System 1 for one stock, on its completed weekly bars.

    Columns: date, close (adjusted), sma, rsi, state, developing.
    """
    df = prices.load_completed_prices(symbol, "weekly")
    close = df["adj_close"]
    sma = indicators.sma(close, SMA_PERIOD)
    rsi = indicators.rsi(close, RSI_PERIOD)
    states, developing = run_state_machine(close.to_list(), sma.to_list(), rsi.to_list())
    out = pd.DataFrame({
        "date": df["date"],
        "close": close,
        "sma": sma,
        "rsi": rsi,
        # dtype=object keeps real None for warm-up bars (pandas 3 would turn
        # None into NaN in a string column).
        "state": pd.Series(states, index=df.index, dtype=object),
        "developing": pd.Series(developing, index=df.index, dtype=bool),
    })
    return out


def signals(symbol: str) -> list[dict]:
    """The BUY and SELL bars, oldest first, for chart markers."""
    rows = evaluate(symbol)
    marked = rows[rows["state"].isin(["BUY", "SELL"])]
    return [
        {"time": d.strftime("%Y-%m-%d"), "state": s, "price": round(float(c), 2)}
        for d, s, c in zip(marked["date"], marked["state"], marked["close"])
    ]


def current_signal(symbol: str) -> dict | None:
    """The newest completed weekly bar's reading, or None if there is no history yet.

    `week_ending` is the date of that bar, so the UI can always say which week
    the signal refers to. `since` is the BUY date if a position is open.
    """
    rows = evaluate(symbol)
    valid = rows[rows["state"].notna()]
    if valid.empty:
        return None
    last = valid.iloc[-1]
    in_position = last["state"] in ("BUY", "HOLD")
    since = None
    if in_position:
        buys = valid[valid["state"] == "BUY"]
        since = buys["date"].iloc[-1].strftime("%Y-%m-%d")
    return {
        "week_ending": last["date"].strftime("%Y-%m-%d"),
        "state": last["state"],
        "developing": bool(last["developing"]),
        "close": round(float(last["close"]), 2),
        "sma": round(float(last["sma"]), 2),
        "rsi": round(float(last["rsi"]), 2),
        "in_position": in_position,
        "since": since,
    }


def all_current_signals() -> dict[str, dict | None]:
    return {symbol: current_signal(symbol) for symbol in TICKERS}


# ---------------------------------------------------------------------------
# Backtest (all money hypothetical)
# Fill rule, chosen by the user (2026-10-03): a trade is bought at the adjusted
# close of the BUY week and sold at the adjusted close of the SELL week.
# ---------------------------------------------------------------------------
def trades_from_rows(rows: pd.DataFrame) -> list[dict]:
    trades: list[dict] = []
    current = None
    for d, state, close in zip(rows["date"], rows["state"], rows["close"]):
        if state == "BUY":
            current = {"entry_date": d, "entry_price": float(close)}
        elif state == "SELL":
            current.update(exit_date=d, exit_price=float(close), open=False)
            trades.append(current)
            current = None
    if current is not None:  # still held at the end of the data: mark to market
        current.update(exit_date=rows["date"].iloc[-1], exit_price=float(rows["close"].iloc[-1]), open=True)
        trades.append(current)
    return trades


def backtest_bars(rows: pd.DataFrame) -> pd.DataFrame:
    """The backtest period: from the first week the system can be evaluated to the newest completed week."""
    valid = rows[rows["state"].notna()]
    return valid[["date", "close"]].reset_index(drop=True)


def _backtest_raw(symbol: str, capital: float) -> dict:
    rows = evaluate(symbol)
    bars = backtest_bars(rows)
    trades = trades_from_rows(rows)
    summary = bt.summarize(trades, bars, capital)
    return {
        "times": bars["date"].dt.strftime("%Y-%m-%d").to_list(),
        "equity": summary.pop("equity"),
        "buy_hold": bt.buy_hold_curve(bars, capital),
        "summary": summary,
        "trades": trades,
    }


def _points(times: list[str], values: list[float]) -> list[dict]:
    return [{"time": t, "value": round(v, 2)} for t, v in zip(times, values)]


def backtest(symbol: str, capital: float) -> dict:
    raw = _backtest_raw(symbol, capital)
    return {
        "summary": raw["summary"],
        "trades": bt.trade_rows(raw["trades"]),
        "equity": _points(raw["times"], raw["equity"]),
        "buy_hold": _points(raw["times"], raw["buy_hold"]),
    }


def portfolio_backtest(capital: float) -> dict:
    """Total capital split equally across the stocks. Each stock's curve is independent;
    money is never moved between stocks. The portfolio curve is their sum."""
    share = capital / len(TICKERS)
    per_stock = {symbol: _backtest_raw(symbol, share) for symbol in TICKERS}
    times = next(iter(per_stock.values()))["times"]
    for symbol, result in per_stock.items():
        if result["times"] != times:
            raise ValueError(f"{symbol} has different weekly dates; cannot sum equity curves")
    equity = [sum(r["equity"][i] for r in per_stock.values()) for i in range(len(times))]
    buy_hold = [sum(r["buy_hold"][i] for r in per_stock.values()) for i in range(len(times))]
    return {
        "summary": {
            "capital": capital,
            "per_stock_capital": share,
            "period_start": times[0],
            "period_end": times[-1],
            "final_equity": equity[-1],
            "total_return": equity[-1] / capital - 1.0,
            "buy_hold_final": buy_hold[-1],
            "buy_hold_return": buy_hold[-1] / capital - 1.0,
            "max_drawdown": bt.max_drawdown(equity),
        },
        "stocks": [
            {"symbol": s, "name": TICKERS[s], **{k: r["summary"][k] for k in (
                "final_equity", "total_return", "buy_hold_return", "max_drawdown",
                "longest_losing_streak", "closed_trades", "win_rate")},
             "open_position": r["summary"]["open_trade"] is not None}
            for s, r in per_stock.items()
        ],
        "equity": _points(times, equity),
        "buy_hold": _points(times, buy_hold),
    }
