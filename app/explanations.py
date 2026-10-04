"""Margin notes: deterministic, template-based explanations (1-2 sentences each).

This is NOT the AI. Every note is a fixed template filled with numbers that were
already computed elsewhere, so there is always an explanation for every reading,
offline, and it can never invent a figure.

Rules for the wording:
- Describe what the rules say and what the numbers are. Never tell anyone to buy,
  sell or hold, and never predict prices.
- Every label a system can produce has exactly one template here. The dicts are
  keyed by label so scripts/verify_explanations.py can prove nothing is missing.
"""
from app.formatting import format_inr, format_pct
from app.rsi_zones import BEARISH_BELOW, BULLISH_ABOVE, FLAT_BAND

EXTENDED_ABOVE = 80.0
EXTENDED_BELOW = 20.0

# ---------------------------------------------------------------------------
# RSI zone (notes page 1): instantaneous reading
# ---------------------------------------------------------------------------
ZONE_NOTES = {
    "Bearish": "An RSI of {rsi} is below 40, the bearish band in the notes: over the last 14 weeks, losses have outweighed gains.",
    "Sideways": "An RSI of {rsi} sits in the 40 to 60 middle band, which the notes read as sideways: gains and losses have been roughly balanced.",
    "Bullish": "An RSI of {rsi} is above 60, the bullish band in the notes: over the last 14 weeks, gains have outweighed losses.",
}

# ---------------------------------------------------------------------------
# RSI trend (notes page 12): behavioural reading
# ---------------------------------------------------------------------------
TREND_NOTES = {
    "Strong Uptrend": "Above 60, the notes read RSI as a strong uptrend by its value alone.{extended}",
    "Strong Downtrend": "Below 40, the notes read RSI as a strong downtrend by its value alone.{extended}",
    "Uptrend": "In the 40 to 60 middle band, direction decides: RSI rose from {prev} a week earlier to {rsi}, so it reads as an uptrend (this middle-band tiebreak is a constructed rule, not taken from the notes).",
    "Downtrend": "In the 40 to 60 middle band, direction decides: RSI fell from {prev} a week earlier to {rsi}, so it reads as a downtrend (this middle-band tiebreak is a constructed rule, not taken from the notes).",
    "Sideways": "In the 40 to 60 middle band, direction decides: RSI moved only from {prev} to {rsi} in a week, within half a point, so it reads as sideways (this middle-band tiebreak is a constructed rule, not taken from the notes).",
}
EXTENDED_HIGH = " At {rsi} it is also above 80, which the notes call extended."
EXTENDED_LOW = " At {rsi} it is also below 20, which the notes call extended."

# ---------------------------------------------------------------------------
# System 1: Trend Following signal states (+ the DEVELOPING flag)
# ---------------------------------------------------------------------------
SYSTEM1_NOTES = {
    "BUY": "In the week ending {week}, both entry conditions held: RSI crossed above 60 (to {rsi}) and the close of {close} finished above the 20-week average of {sma}. Under these rules a position opens at that close.",
    "HOLD": "A position has been open since the week ending {since}, and the close of {close} is still at or above the 20-week average of {sma}. The rules keep holding while that is true; the average works as the trailing stop.",
    "SELL": "The close of {close} fell below the 20-week average of {sma}, which is this system's exit rule. Under these rules the position closes at that week's close.",
    "NEUTRAL": "No position is open, and this week did not meet the entry conditions (RSI crossing above 60 with the close above the 20-week average). RSI is {rsi}, and the close of {close} is {side} the average of {sma}.",
    "DEVELOPING": "Not an entry, but conditions are building: the close is above the 20-week average and RSI ({rsi}) is between 50 and 60 and rising. An entry would still need RSI to cross above 60.",
}

# ---------------------------------------------------------------------------
# System 3: Value Buy states (SELL split by exit reason)
# ---------------------------------------------------------------------------
VALUE_BUY_NOTES = {
    "NEUTRAL": "No Value Buy setup is armed: it needs monthly RSI between 38 and 45 and rising, then a green weekly candle. The latest completed month ({month}) had RSI {rsi} against {prev} the month before, {context_tail}.",
    "ARMED": "The green week ending {signal} formed while the monthly context was active, so a stop-buy is armed at its high of {level}, with the stop at its low of {stop}. It triggers only if a later week trades above {level}, and lapses after {weeks_left}.",
    "BUY": "This week traded above the stop-buy, so under these rules a position opens at {entry}. The stop is fixed at {stop} and the target is the recent swing high of {target}, a reward-to-risk of {ratio} to 1.",
    "HOLD": "A position has been open since the week ending {entry_week} at {entry}. Under these rules it closes at the stop of {stop} or the target of {target}, whichever is reached first, and the stop never moves.",
    "SELL:stop": "This week fell to the fixed stop of {stop}, so under these rules the position closes there, {ret} from the entry at {entry}.",
    "SELL:target": "This week reached the target of {target}, so under these rules the position closes there, {ret} from the entry at {entry}.",
}
CONTEXT_ACTIVE_TAIL = "so the context is active but no green weekly candle has armed a setup"
CONTEXT_INACTIVE_TAIL = "so the context is not active"

# ---------------------------------------------------------------------------
# System 2: Cup & Handle (detector output is only ever a POSSIBLE formation)
# ---------------------------------------------------------------------------
CUP_NOTES = {
    "NONE": "No possible cup formation is detected in the completed monthly data up to {as_of}. The rules need a cup of at least 5 years whose right rim comes back within 8% of the left rim, plus a rounded bottom and a shallow handle, and steadily rising stocks rarely form one.",
    "POSSIBLE": "The detector sees a possible {months}-month cup from {left} to {right}, {depth} deep, with a handle from {handle_start} to {handle_end}. Detection is approximate, so the chart needs a human review; no levels are shown until the cup is confirmed.",
    "CONFIRMED": "This cup has been confirmed. Under the rules the buy point is the handle's high of {buy_point}, the stop-buy sits 4% above it at {entry}{trigger_text}, and the stop is fixed at {stop}.",
}
CUP_TRIGGER_TEXT = " (crossed in the month ending {date})"
CUP_PENDING_TEXT = " (not crossed yet)"


def cup_key(status: dict, confirmed: bool) -> str:
    if status["status"] == "NONE":
        return "NONE"
    return "CONFIRMED" if confirmed else "POSSIBLE"


def cup_note(status: dict, confirmed: bool) -> str:
    key = cup_key(status, confirmed)
    if key == "NONE":
        return CUP_NOTES["NONE"].format(as_of=status.get("as_of") or "the end of the data")
    c, lv = status["cup"], status["levels"]
    trigger = CUP_TRIGGER_TEXT.format(date=lv["entry_date"]) if lv["entry_triggered"] else CUP_PENDING_TEXT
    return CUP_NOTES[key].format(
        months=c["months"], left=c["left_rim_date"], right=c["right_rim_date"],
        depth=f"{c['depth'] * 100:.1f}%", handle_start=c["handle_start"], handle_end=c["handle_end"],
        buy_point=format_inr(lv["buy_point"]), entry=format_inr(lv["entry"]), stop=format_inr(lv["stop"]),
        trigger_text=trigger,
    )


# ---------------------------------------------------------------------------
# Backtest summaries
# ---------------------------------------------------------------------------
MATCH_BAND_POINTS = 1.0  # within this many percentage points counts as "roughly matched"

BACKTEST_NOTES = {
    "trailed": "From {start} to {end}, these rules turned {capital} into {final} ({ret}{open}); buying and holding over the same {unit} would have reached {bh_final} ({bh_ret}). The system trailed buy-and-hold by {gap} percentage points, and its deepest fall along the way was {dd}.",
    "beat": "From {start} to {end}, these rules turned {capital} into {final} ({ret}{open}); buying and holding over the same {unit} would have reached {bh_final} ({bh_ret}). The system beat buy-and-hold by {gap} percentage points, and its deepest fall along the way was {dd}.",
    "matched": "From {start} to {end}, these rules turned {capital} into {final} ({ret}{open}), roughly the same as buying and holding over the same {unit} ({bh_final}, {bh_ret}). Its deepest fall along the way was {dd}.",
    "no_trades": "No trades happened from {start} to {end}, so the capital simply stayed at {capital}. Buying and holding over the same {unit} would have reached {bh_final} ({bh_ret}).",
}
OPEN_POSITION = ", counting one position still open at the end at the last close"
PORTFOLIO_PREFIX = "Across all five stocks together: "


def _num(x: float) -> str:
    return f"{x:.2f}"


def rsi_zone_note(zone: str, rsi: float) -> str:
    return ZONE_NOTES[zone].format(rsi=_num(rsi))


def rsi_trend_note(trend: str, rsi: float, rsi_week_ago: float | None) -> str:
    extended = ""
    if trend == "Strong Uptrend" and rsi > EXTENDED_ABOVE:
        extended = EXTENDED_HIGH.format(rsi=_num(rsi))
    elif trend == "Strong Downtrend" and rsi < EXTENDED_BELOW:
        extended = EXTENDED_LOW.format(rsi=_num(rsi))
    prev = _num(rsi_week_ago) if rsi_week_ago is not None else "n/a"
    return TREND_NOTES[trend].format(rsi=_num(rsi), prev=prev, extended=extended)


def system1_note(current: dict) -> str:
    """Note for System 1's current reading (the dict from trend_following.current_signal)."""
    key = "DEVELOPING" if current["state"] == "NEUTRAL" and current["developing"] else current["state"]
    side = "above" if current["close"] > current["sma"] else "below" if current["close"] < current["sma"] else "exactly at"
    return SYSTEM1_NOTES[key].format(
        week=current["week_ending"],
        rsi=_num(current["rsi"]),
        close=format_inr(current["close"]),
        sma=format_inr(current["sma"]),
        since=current.get("since") or "",
        side=side,
    )


def value_buy_key(current: dict) -> str:
    return f"SELL:{current['exit_reason']}" if current["state"] == "SELL" else current["state"]


def value_buy_note(current: dict) -> str:
    """Note for Value Buy's current reading (the dict from value_buy.current_signal)."""
    key = value_buy_key(current)
    ctx, a, p = current["context"], current.get("armed") or {}, current.get("position") or {}
    weeks_left = a.get("weeks_left")
    fields = {
        "month": ctx["month"] or "not available",
        "rsi": _num(ctx["rsi"]) if ctx["rsi"] is not None else "not available",
        "prev": _num(ctx["prev_rsi"]) if ctx["prev_rsi"] is not None else "not available",
        "context_tail": CONTEXT_ACTIVE_TAIL if ctx["active"] else CONTEXT_INACTIVE_TAIL,
        "signal": a.get("signal_week", ""),
        "level": format_inr(a["level"]) if a else "",
        "stop": format_inr(a["stop"]) if a else format_inr(p["stop"]) if p else "",
        "weeks_left": (f"{weeks_left} more week" + ("" if weeks_left == 1 else "s")) if weeks_left else "",
        "entry": format_inr(p["entry"]) if p else "",
        "entry_week": p.get("entry_week", ""),
        "target": format_inr(p["target"]) if p else "",
        "ratio": f"{p['ratio']:.2f}" if p and p.get("ratio") is not None else "",
        "ret": format_pct(p["exit_price"] / p["entry"] - 1) if p and p.get("exit_price") else "",
    }
    return VALUE_BUY_NOTES[key].format(**fields)


def backtest_outcome(summary: dict) -> str:
    """Which BACKTEST_NOTES template applies to a summary."""
    if summary.get("closed_trades", 1) == 0 and summary.get("open_trade") is None:
        return "no_trades"
    gap = (summary["total_return"] - summary["buy_hold_return"]) * 100
    if abs(gap) < MATCH_BAND_POINTS:
        return "matched"
    return "beat" if gap > 0 else "trailed"


def backtest_note(summary: dict, portfolio: bool = False, unit: str = "weeks") -> str:
    """`unit` names the bars the backtest walked: "weeks" (Systems 1 and 3) or "months" (Cup & Handle)."""
    outcome = backtest_outcome(summary)
    gap = abs(summary["total_return"] - summary["buy_hold_return"]) * 100
    text = BACKTEST_NOTES[outcome].format(
        start=summary["period_start"],
        end=summary["period_end"],
        capital=format_inr(summary["capital"]),
        final=format_inr(summary["final_equity"]),
        ret=format_pct(summary["total_return"]),
        bh_final=format_inr(summary["buy_hold_final"]),
        bh_ret=format_pct(summary["buy_hold_return"]),
        gap=f"{gap:.1f}",
        dd=format_pct(summary["max_drawdown"]),
        open=OPEN_POSITION if summary.get("open_trade") else "",
        unit=unit,
    )
    return PORTFOLIO_PREFIX + text[0].lower() + text[1:] if portfolio else text


# Sanity: the thresholds quoted in the wording are the ones the code actually uses.
assert (BEARISH_BELOW, BULLISH_ABOVE, FLAT_BAND) == (40.0, 60.0, 0.5), "update the note wording"
