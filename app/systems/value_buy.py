"""System 3: Value Buy, a technical pullback entry. Rules from the user's notes (BUILD.md section 12).

NOT fundamental value investing: no P/E, no book value, no company financials.
"Value" means buying a pullback (weakness) on the chart. Kept separate from System 1,
which buys strength with a trailing stop and no target; this system buys weakness with
a FIXED stop and a DEFINED target.

Timeframes: monthly = context filter, weekly = trigger and execution.

Entry, only when flat, one position at a time:
  1. Context:   monthly RSI(14) between 38 and 45 AND rising versus the prior month.
                Falling into the range does not count.
  2. Trigger:   a weekly candle closes green (close > open) while context is active.
                That candle is the "signal candle".
  3. Execution: arm a stop-buy at the signal candle's HIGH. Entry happens only when a
                LATER week's high trades above it; entry price = that level (a pending
                stop order, not the later week's own price). The setup expires after
                2 weeks untriggered. A new signal candle while armed re-arms at the new
                high and restarts the 2 weeks.
Exit, a bracket (whichever is hit first):
  - Stop:   the signal candle's LOW, fixed, never trails.
  - Target: the highest-value swing high (high above both immediate neighbours) in the
            prior 20 weekly bars. If that target is at or below the entry price, the
            entry is skipped and the setup stays armed.
Risk-reward is a fixed snapshot at entry: risk = entry - stop, reward = target - entry,
ratio = reward / risk. The all-time high is shown as secondary context only.

Implementation choices where the notes are silent (flagged so they are easy to change):
  - A week sees the newest COMPLETED month whose month-end is on or before the week's
    Friday (an as-of join; never a month that was still running: no lookahead).
  - "Between 38 and 45" includes both ends; "rising" means strictly above last month.
  - The target is looked up when the stop-buy triggers, from the 20 weeks before that
    week. A swing high needs the following week to confirm it, so the newest usable
    swing is two weeks back.
  - Exits fill at the stop / target level. If one week touches both, the stop is
    assumed to come first (we cannot know the order inside a week; this is the
    cautious choice). Exits are checked from the week after entry.
  - Prices are ADJUSTED (open/high/low scaled by adj_close / close, as on the chart).
"""
import bisect
import math

import pandas as pd

from app import indicators, prices
from app.systems import backtest as bt

RSI_PERIOD = 14
CONTEXT_LOW = 38.0
CONTEXT_HIGH = 45.0
ARM_WEEKS = 2
SWING_LOOKBACK = 20

STATES = ("NEUTRAL", "ARMED", "BUY", "HOLD", "SELL")
EXIT_REASONS = ("stop", "target")


adjusted_ohlc = prices.adjusted_ohlc  # shared with Cup & Handle


def is_context_active(rsi: float, prev_rsi: float) -> bool:
    """Monthly RSI between 38 and 45 (inclusive) AND higher than last month.
    Falling into the range does not count. Unknown values (NaN) never count."""
    if rsi is None or prev_rsi is None or math.isnan(rsi) or math.isnan(prev_rsi):
        return False
    return CONTEXT_LOW <= rsi <= CONTEXT_HIGH and rsi > prev_rsi


def monthly_context(symbol: str) -> pd.DataFrame:
    """Completed months with RSI(14), the prior month's RSI, and whether context is active."""
    m = prices.load_completed_prices(symbol, "monthly")
    rsi = indicators.rsi(m["adj_close"], RSI_PERIOD)
    prev = rsi.shift(1)
    active = [is_context_active(float(r), float(p)) for r, p in zip(rsi, prev)]
    return pd.DataFrame({"date": m["date"], "rsi": rsi, "prev_rsi": prev, "active": active})


def join_context(week_dates: pd.Series, months: pd.DataFrame) -> pd.DataFrame:
    """For each week, the newest month whose month-end is on or before that week's date."""
    month_dates = list(months["date"])
    rows = []
    for w in week_dates:
        k = bisect.bisect_right(month_dates, w) - 1
        if k < 0:
            rows.append({"month": pd.NaT, "rsi": math.nan, "prev_rsi": math.nan, "active": False})
        else:
            r = months.iloc[k]
            rows.append({"month": r["date"], "rsi": r["rsi"], "prev_rsi": r["prev_rsi"], "active": bool(r["active"])})
    return pd.DataFrame(rows, index=week_dates.index)


def swing_target(highs: list[float], i: int, lookback: int = SWING_LOOKBACK) -> float | None:
    """Highest swing high among the `lookback` weeks before week i, using only weeks
    already confirmed by their right-hand neighbour before week i (so j <= i - 2)."""
    best = None
    for j in range(max(1, i - lookback), i - 1):
        if highs[j] > highs[j - 1] and highs[j] > highs[j + 1]:
            if best is None or highs[j] > best:
                best = highs[j]
    return best


def run_weekly_state_machine(ohlc: dict, context: list[bool], swing_lookback: int = SWING_LOOKBACK):
    """Walk the weeks in order.

    ohlc: dict of equal-length lists: open, high, low, close (adjusted).
    context: one bool per week: is the monthly context active for that week?
    Returns (rows, trades): one row per week {state, exit_reason, armed, position}
    and the trades as dicts with week indexes (entry_idx, exit_idx; exit_idx None if open).
    """
    o, h, lo, c = ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"]
    rows, trades = [], []
    armed = None     # {signal_idx, level, stop, until}
    pos = None       # {signal_idx, entry_idx, entry, stop, target}

    for i in range(len(c)):
        state, reason = None, None
        if pos is not None:
            hit_stop = lo[i] <= pos["stop"]
            hit_target = h[i] >= pos["target"]
            if hit_stop or hit_target:
                reason = "stop" if hit_stop else "target"   # both in one week: stop first (cautious)
                trades.append({**pos, "exit_idx": i, "exit_price": pos[reason], "exit_reason": reason})
                pos, state = None, "SELL"
            else:
                state = "HOLD"
        else:
            entered = False
            if armed is not None and armed["signal_idx"] < i <= armed["until"] and h[i] > armed["level"]:
                target = swing_target(h, i, swing_lookback)
                if target is not None and target > armed["level"]:
                    pos = {"signal_idx": armed["signal_idx"], "entry_idx": i, "entry": armed["level"],
                           "stop": armed["stop"], "target": target}
                    armed, state, entered = None, "BUY", True
                # otherwise: no usable target above the entry, so the setup simply stays armed
            if not entered:
                if context[i] and c[i] > o[i]:
                    armed = {"signal_idx": i, "level": h[i], "stop": lo[i], "until": i + ARM_WEEKS}
                elif armed is not None and i >= armed["until"]:
                    armed = None   # two weeks passed without a trigger: expired
                state = "ARMED" if armed is not None else "NEUTRAL"
        rows.append({"state": state, "exit_reason": reason,
                     "armed": dict(armed) if armed else None, "position": dict(pos) if pos else None})

    if pos is not None:
        trades.append({**pos, "exit_idx": None, "exit_price": None, "exit_reason": None})
    return rows, trades


def evaluate(symbol: str, swing_lookback: int = SWING_LOOKBACK) -> dict:
    """Value Buy for one stock on completed weekly bars."""
    weekly = adjusted_ohlc(prices.load_completed_prices(symbol, "weekly"))
    ctx = join_context(weekly["date"], monthly_context(symbol))
    ohlc = {k: weekly[k].to_list() for k in ("open", "high", "low", "close")}
    rows, trades = run_weekly_state_machine(ohlc, ctx["active"].to_list(), swing_lookback)
    return {"weekly": weekly, "context": ctx, "rows": rows, "trades": trades}


def _risk_reward(entry: float, stop: float, target: float) -> dict:
    risk, reward = entry - stop, target - entry
    return {"risk": risk, "reward": reward, "ratio": reward / risk if risk > 0 else None}


def _date(weekly: pd.DataFrame, i: int) -> str:
    return weekly["date"].iloc[i].strftime("%Y-%m-%d")


def current_signal(symbol: str) -> dict:
    ev = evaluate(symbol)
    weekly, ctx, rows = ev["weekly"], ev["context"], ev["rows"]
    last = len(rows) - 1
    row, c = rows[last], ctx.iloc[last]
    out = {
        "week_ending": _date(weekly, last),
        "state": row["state"],
        "exit_reason": row["exit_reason"],
        "context": {
            "month": None if pd.isna(c["month"]) else c["month"].strftime("%Y-%m-%d"),
            "rsi": None if math.isnan(c["rsi"]) else round(float(c["rsi"]), 2),
            "prev_rsi": None if math.isnan(c["prev_rsi"]) else round(float(c["prev_rsi"]), 2),
            "active": bool(c["active"]),
        },
        "armed": None,
        "position": None,
        "all_time_high": round(float(weekly["high"].max()), 2),
        "all_time_high_week": _date(weekly, int(weekly["high"].idxmax())),
    }
    if row["armed"]:
        a = row["armed"]
        out["armed"] = {
            "signal_week": _date(weekly, a["signal_idx"]),
            "level": round(a["level"], 2),
            "stop": round(a["stop"], 2),
            "weeks_left": a["until"] - last,
        }
    if row["position"] or row["state"] == "SELL":
        t = row["position"] or next(tr for tr in reversed(ev["trades"]) if tr["exit_idx"] == last)
        out["position"] = {
            "signal_week": _date(weekly, t["signal_idx"]),
            "entry_week": _date(weekly, t["entry_idx"]),
            "entry": round(t["entry"], 2),
            "stop": round(t["stop"], 2),
            "target": round(t["target"], 2),
            "last_close": round(float(weekly["close"].iloc[last]), 2),
            **{k: (round(v, 2) if v is not None else None) for k, v in _risk_reward(t["entry"], t["stop"], t["target"]).items()},
        }
        if row["state"] == "SELL":
            out["position"]["exit_price"] = round(t[row["exit_reason"]], 2)
    return out


# ---------------------------------------------------------------------------
# Backtest (all money hypothetical). Uses the shared engine in backtest.py.
# ---------------------------------------------------------------------------
def _engine_trades(ev: dict) -> list[dict]:
    weekly = ev["weekly"]
    out = []
    last = len(weekly) - 1
    for t in ev["trades"]:
        is_open = t["exit_idx"] is None
        x = last if is_open else t["exit_idx"]
        out.append({
            "entry_date": weekly["date"].iloc[t["entry_idx"]],
            "entry_price": t["entry"],
            "exit_date": weekly["date"].iloc[x],
            "exit_price": float(weekly["close"].iloc[last]) if is_open else t["exit_price"],
            "open": is_open,
            "signal_date": _date(weekly, t["signal_idx"]),
            "stop": t["stop"],
            "target": t["target"],
            "exit_reason": t["exit_reason"],
            **_risk_reward(t["entry"], t["stop"], t["target"]),
        })
    return out


def backtest_bars(ev: dict) -> pd.DataFrame:
    """The period: from the first week whose monthly context can be judged
    (this month's and last month's RSI both known) to the newest completed week."""
    ctx = ev["context"]
    known = ctx["rsi"].notna() & ctx["prev_rsi"].notna()
    start = int(known.to_numpy().argmax()) if known.any() else 0
    w = ev["weekly"].iloc[start:]
    return pd.DataFrame({"date": w["date"], "close": w["close"]}).reset_index(drop=True)


def backtest(symbol: str, capital: float) -> dict:
    ev = evaluate(symbol)
    bars = backtest_bars(ev)
    trades = _engine_trades(ev)
    summary = bt.summarize(trades, bars, capital)
    times = bars["date"].dt.strftime("%Y-%m-%d").to_list()
    equity = summary.pop("equity")
    rows = bt.trade_rows(trades)
    for r in rows:
        for k in ("entry_price", "exit_price", "stop", "target", "risk", "reward", "ratio"):
            if r.get(k) is not None:
                r[k] = round(r[k], 2)
    return {
        "summary": summary,
        "trades": rows,
        "equity": [{"time": t, "value": round(v, 2)} for t, v in zip(times, equity)],
        "buy_hold": [{"time": t, "value": round(v, 2)} for t, v in zip(times, bt.buy_hold_curve(bars, capital))],
    }
