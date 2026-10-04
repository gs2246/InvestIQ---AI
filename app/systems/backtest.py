"""Shared backtest helpers, used by EVERY system so compounding works the same everywhere.

All money is HYPOTHETICAL. No transaction costs, no taxes, no slippage.

A trade is a dict with at least:
    entry_date, entry_price, exit_date, exit_price, open
where an OPEN trade (still held at the end of the data) has exit_date / exit_price
set to the last bar's date and close, i.e. it is marked to market.
Systems may add their own fields (exit_reason, tranches, ...); they are passed through.

Compounding rules:
    - Capital compounds trade to trade: each trade puts ALL of the stock's current
      capital in at the entry price.
    - While not in a position the capital sits flat (no interest, no return).
    - One position at a time.

`bars` is a DataFrame with columns date (datetime64) and close (adjusted), the
completed weekly bars over the backtest period. The period is the same for the
strategy and the buy-and-hold benchmark.
"""
import math

import pandas as pd


def trade_return(trade: dict) -> float:
    return trade["exit_price"] / trade["entry_price"] - 1.0


def compound_equity_curve(trades: list[dict], bars: pd.DataFrame, capital: float) -> list[float]:
    """Equity at each bar's close.

    During a trade: capital at entry x close / entry price.
    On the exit bar: capital at entry x exit price / entry price (the new capital).
    Outside trades: unchanged.
    """
    index_of = {d: i for i, d in enumerate(bars["date"])}
    closes = bars["close"].to_list()
    equity = [capital] * len(closes)
    cash = capital
    cursor = 0  # first bar not yet written

    for t in sorted(trades, key=lambda t: t["entry_date"]):
        e, x = index_of[t["entry_date"]], index_of[t["exit_date"]]
        if e < cursor:
            raise ValueError("trades overlap: only one position at a time is allowed")
        for i in range(cursor, e):
            equity[i] = cash
        # ratio first: on the entry bar close / entry is exactly 1.0, so equity does not
        # wobble in the last binary digit when nothing has actually changed
        for i in range(e, x):
            equity[i] = cash * (closes[i] / t["entry_price"])
        cash = cash * (t["exit_price"] / t["entry_price"])
        equity[x] = cash
        cursor = x + 1
    for i in range(cursor, len(closes)):
        equity[i] = cash
    return equity


def max_drawdown(equity: list[float]) -> float:
    """Largest peak-to-trough fall, as a fraction <= 0 (e.g. -0.35 means 35% down)."""
    peak, worst = -math.inf, 0.0
    for v in equity:
        peak = max(peak, v)
        worst = min(worst, v / peak - 1.0)
    return worst


def longest_losing_streak(trades: list[dict]) -> int:
    """Most consecutive CLOSED trades with a negative return (open trades excluded)."""
    best = run = 0
    for t in sorted(trades, key=lambda t: t["entry_date"]):
        if t["open"]:
            continue
        run = run + 1 if trade_return(t) < 0 else 0
        best = max(best, run)
    return best


def summarize(trades: list[dict], bars: pd.DataFrame, capital: float) -> dict:
    equity = compound_equity_curve(trades, bars, capital)
    closed = [t for t in trades if not t["open"]]
    open_trades = [t for t in trades if t["open"]]
    closed_returns = [trade_return(t) for t in closed]
    wins = sum(1 for r in closed_returns if r > 0)

    # Capital after closed trades only (the open trade marked separately).
    realised = capital
    for r in closed_returns:
        realised *= 1.0 + r

    start_close, end_close = float(bars["close"].iloc[0]), float(bars["close"].iloc[-1])
    buy_hold_return = end_close / start_close - 1.0

    return {
        "capital": capital,
        "period_start": bars["date"].iloc[0].strftime("%Y-%m-%d"),
        "period_end": bars["date"].iloc[-1].strftime("%Y-%m-%d"),
        "final_equity": equity[-1],
        "total_return": equity[-1] / capital - 1.0,
        "buy_hold_return": buy_hold_return,
        "buy_hold_final": capital * (1.0 + buy_hold_return),
        "max_drawdown": max_drawdown(equity),
        "longest_losing_streak": longest_losing_streak(trades),
        "closed_trades": len(closed),
        "wins": wins,
        "losses": sum(1 for r in closed_returns if r < 0),
        "win_rate": wins / len(closed) if closed else None,
        "realised_equity": realised,
        "open_trade": (
            {
                "entry_date": open_trades[0]["entry_date"].strftime("%Y-%m-%d"),
                "entry_price": open_trades[0]["entry_price"],
                "marked_price": open_trades[0]["exit_price"],
                "unrealised_return": trade_return(open_trades[0]),
            }
            if open_trades else None
        ),
        "equity": equity,
    }


def buy_hold_curve(bars: pd.DataFrame, capital: float) -> list[float]:
    start = float(bars["close"].iloc[0])
    return [capital * c / start for c in bars["close"]]


def trade_rows(trades: list[dict]) -> list[dict]:
    """Trades as JSON-ready rows for a trade log."""
    rows = []
    for t in sorted(trades, key=lambda t: t["entry_date"]):
        row = {k: v for k, v in t.items() if k not in ("entry_date", "exit_date")}
        row["entry_date"] = t["entry_date"].strftime("%Y-%m-%d")
        row["exit_date"] = t["exit_date"].strftime("%Y-%m-%d")
        row["return"] = trade_return(t)
        rows.append(row)
    return rows


def validate_capital(capital: float) -> str | None:
    """A plain-English problem with the capital, or None if it is usable."""
    if capital is None or not math.isfinite(capital):
        return "Capital must be a number."
    if capital <= 0:
        return "Capital must be more than zero."
    if capital > 1e13:
        return "Capital is too large to be meaningful here."
    return None
