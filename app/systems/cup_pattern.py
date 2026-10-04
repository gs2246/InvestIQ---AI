"""System 2: Cup & Handle. Rules from the user's notes (BUILD.md section 11).

Monthly candles (completed months, adjusted prices). Minimum 5-year cup.

Cup geometry
  - Left rim:  a local high, the highest high within +/-3 months.
  - Bottom:    the lowest low after the left rim (up to the right rim).
  - Right rim: a later local high (same +/-3-month test) within 8% of the left rim's high.
  - Duration:  left rim -> right rim >= 60 months.
  - Depth:     the bottom is 12-50% below the left rim's high.
  - Rounded bottom: the lowest quarter of the cup's price range holds >= 20% of the
    cup's duration (time spent near the bottom, not a V spike).
Handle (required; a cup without a qualifying handle is not a complete setup, and the
next right-rim candidate is checked instead)
  - USER DECISION (2026-10-04): the handle is the pullback after the right rim. It ends
    at the first month whose high gets back above the right rim's high.
  - It must last 1-6 months and retrace less than 1/3 of the cup's depth (measured down
    from the right rim's high), which also keeps it in the upper third of the cup.
Entry / stop, relative to the BUY POINT = the handle's highest high
  - Entry = buy point x 1.04 as a pending stop order: it fills only when a later month's
    high trades above it, at that level. No expiry.
  - Stop = buy point x 0.76, fixed at entry.
Selling ladders (three independent modes, same entry and stop)
  - income: sell 1/3 at +10% and 1/3 at +20%, hold the last 1/3; the original stop is
            never raised.
  - wealth: sell 1/3 at +20% and 1/3 at +40%, hold the last 1/3; the stop trails: the first
            +10% milestone raises it to +10%, every later milestone M to M - 10%
            (+20% -> +10%, +30% -> +20%, ... +110% -> +100%), indefinitely.
  - trail:  the wealth stop ladder with no partial sells.

Choices where the notes are silent (cautious; listed so they are easy to change):
  - Rounded bottom is measured with monthly CLOSES.
  - No lookahead: a right rim is only known once the 3 months after it exist, and the
    handle only once the month that regains the rim exists. The stop-buy can fill from
    the month after both are known.
  - Inside one month the order of high and low is unknown, so the stop is checked first,
    using the stop in force at the start of the month; stop raises from that month's high
    apply from the next month. Exits are checked from the month after entry.
  - Fills are at the exact levels (trigger, targets, stop).

HONESTY (hard requirement): detection is fuzzy and 5-year cups are rare. The UI shows a
detected setup only as "POSSIBLE cup formation - review the chart", and its levels only
after a human confirms it. On the five stocks' real data, these strict thresholds find no
cups; that is the expected, correct result. Do not loosen the thresholds to "find" some.
"""
from app import prices
from app.systems import backtest as bt

RIM_WINDOW = 3                 # months either side for a local high
RIM_SYMMETRY = 0.08            # right rim within 8% of the left rim's high
MIN_CUP_MONTHS = 60
DEPTH_MIN = 0.12
DEPTH_MAX = 0.50
BOTTOM_QUARTILE = 0.25         # "lowest quarter of the cup's price range"
BOTTOM_DWELL_FRAC = 0.20       # ...must hold >= 20% of the cup's months
HANDLE_MIN_MONTHS = 1
HANDLE_MAX_MONTHS = 6
HANDLE_MAX_RETRACE = 1 / 3     # of cup depth
ENTRY_MULT = 1.04
STOP_MULT = 0.76

MODES = ("income", "wealth", "trail")
MODE_LABELS = {"income": "Income", "wealth": "Wealth", "trail": "Trail"}


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------
def local_highs(highs: list[float], window: int = RIM_WINDOW) -> list[int]:
    """Indexes whose high is the highest within +/-window months. Needs the full window
    on both sides, so the newest `window` months can never be (confirmed) local highs."""
    out = []
    for i in range(window, len(highs) - window):
        if highs[i] == max(highs[i - window:i + window + 1]):
            out.append(i)
    return out


def _handle(highs, lows, r):
    """Months after right rim r until a month's high regains the rim. Returns
    (handle_start, handle_end, regain_month) or None if the rim is never regained."""
    for x in range(r + 1, len(highs)):
        if highs[x] > highs[r]:
            return r + 1, x - 1, x
    return None


def detect_cups(ohlc: dict) -> list[dict]:
    """All complete cup-with-handle setups, one per left rim (its first qualifying right rim).

    ohlc: dict of equal-length lists open, high, low, close (adjusted, completed months).
    """
    h, lo, c = ohlc["high"], ohlc["low"], ohlc["close"]
    rims = local_highs(h)
    cups, seen = [], set()
    for li in rims:
        for r in rims:
            if r - li < MIN_CUP_MONTHS:
                continue
            if abs(h[r] - h[li]) / h[li] > RIM_SYMMETRY:
                continue
            b = min(range(li + 1, r), key=lambda k: lo[k])
            depth = (h[li] - lo[b]) / h[li]
            if not DEPTH_MIN <= depth <= DEPTH_MAX:
                continue
            band_top = lo[b] + BOTTOM_QUARTILE * (h[li] - lo[b])
            months = r - li + 1
            dwell = sum(1 for k in range(li, r + 1) if c[k] <= band_top) / months
            if dwell < BOTTOM_DWELL_FRAC:
                continue
            handle = _handle(h, lo, r)
            if handle is None:
                continue                      # the rim was never regained: handle still forming
            hs, he, regain = handle
            length = he - hs + 1
            if not HANDLE_MIN_MONTHS <= length <= HANDLE_MAX_MONTHS:
                continue
            handle_low = min(lo[hs:he + 1])
            if (h[r] - handle_low) >= HANDLE_MAX_RETRACE * (h[li] - lo[b]):
                continue
            if (r, regain) in seen:
                break                         # same rim and handle as an earlier (larger) cup
            seen.add((r, regain))
            buy_point = max(h[hs:he + 1])
            cups.append({
                "left_rim": li, "bottom": b, "right_rim": r,
                "handle_start": hs, "handle_end": he, "regain": regain,
                "depth": depth, "dwell": dwell, "handle_low": handle_low,
                "buy_point": buy_point,
                "entry_level": buy_point * ENTRY_MULT,
                "stop": buy_point * STOP_MULT,
                # first month the stop-buy may fill: after the rim is confirmed (r + window)
                # and after the regain month that ends the handle
                "first_entry_month": max(regain, r + RIM_WINDOW) + 1,
            })
            break                             # first qualifying right rim for this left rim
    return cups


def find_entry(cup: dict, highs: list[float]) -> int | None:
    """Pending stop order: first month at or after first_entry_month whose high trades
    above the entry level. The fill price is the level itself. No expiry."""
    for m in range(cup["first_entry_month"], len(highs)):
        if highs[m] > cup["entry_level"]:
            return m
    return None


# ---------------------------------------------------------------------------
# Selling ladders
# ---------------------------------------------------------------------------
def _milestones_reached(high: float, entry: float) -> int:
    """How many +10% steps the month's high reached (0 if below +10%)."""
    k = 0
    while high >= entry * (1 + 0.10 * (k + 1)) - 1e-9:
        k += 1
    return k


def trailing_stop_pct(milestone: int) -> float | None:
    """Wealth/Trail stop (as a gain over entry) after reaching milestone k (k x 10%)."""
    if milestone <= 0:
        return None
    return 0.10 if milestone == 1 else round(0.10 * (milestone - 1), 10)  # 0.3, not 0.30000000000000004


SELLS = {"income": [(0.10, 1 / 3), (0.20, 1 / 3)], "wealth": [(0.20, 1 / 3), (0.40, 1 / 3)], "trail": []}


def simulate(mode: str, entry_idx: int, entry: float, stop: float, ohlc: dict) -> list[dict]:
    """Walk the months after entry. Returns tranches:
    [{fraction, exit_idx (None if still held), exit_price, reason}]."""
    h, lo, c = ohlc["high"], ohlc["low"], ohlc["close"]
    sells = list(SELLS[mode])
    remaining = 1.0
    tranches = []
    cur_stop = stop
    best_milestone = 0
    for m in range(entry_idx + 1, len(c)):
        # 1. the stop in force at the start of the month comes first
        if lo[m] <= cur_stop:
            tranches.append({"fraction": remaining, "exit_idx": m, "exit_price": cur_stop, "reason": "stop"})
            return tranches
        # 2. partial sells at the milestone levels reached by this month's high
        for gain, frac in list(sells):
            if h[m] >= entry * (1 + gain) - 1e-9:
                tranches.append({"fraction": frac, "exit_idx": m, "exit_price": entry * (1 + gain),
                                 "reason": f"+{round(gain * 100)}% target"})
                remaining -= frac
                sells.remove((gain, frac))
        # 3. the trailing stop rises for next month (wealth and trail only)
        if mode in ("wealth", "trail"):
            best_milestone = max(best_milestone, _milestones_reached(h[m], entry))
            pct = trailing_stop_pct(best_milestone)
            if pct is not None:
                cur_stop = max(cur_stop, entry * (1 + pct))
    if remaining > 1e-12:
        tranches.append({"fraction": remaining, "exit_idx": None, "exit_price": None, "reason": "open"})
    return tranches


def blend(tranches: list[dict], entry: float, last_close: float) -> tuple[float, bool]:
    """One blended exit price (fraction-weighted; open part valued at the last close)."""
    value = sum(t["fraction"] * (last_close if t["exit_idx"] is None else t["exit_price"]) for t in tranches)
    return value, any(t["exit_idx"] is None for t in tranches)


# ---------------------------------------------------------------------------
# Per-stock evaluation, backtest and current status
# ---------------------------------------------------------------------------
def monthly_ohlc(symbol: str) -> tuple[dict, list]:
    df = prices.adjusted_ohlc(prices.load_completed_prices(symbol, "monthly"))
    return {k: df[k].to_list() for k in ("open", "high", "low", "close")}, df["date"].to_list()


def trades_for_mode(cups: list[dict], ohlc: dict, dates: list, mode: str) -> list[dict]:
    """Engine-ready trades: one position at a time, walked in ENTRY order (overlapping cups
    can resolve out of left-rim order). Each multi-tranche trade is collapsed to a blended
    exit so the shared backtest helpers work unchanged; tranches are kept for the UI."""
    h, c = ohlc["high"], ohlc["close"]
    last = len(c) - 1
    candidates = []
    for cup in cups:
        e = find_entry(cup, h)
        if e is not None:
            candidates.append((e, cup))
    candidates.sort(key=lambda pair: pair[0])
    trades, busy_until = [], -1
    for e, cup in candidates:
        if e <= busy_until:
            continue                                  # already in a position
        tranches = simulate(mode, e, cup["entry_level"], cup["stop"], ohlc)
        exit_price, is_open = blend(tranches, cup["entry_level"], c[last])
        exit_idx = last if is_open else max(t["exit_idx"] for t in tranches)
        trades.append({
            "entry_date": dates[e], "entry_price": cup["entry_level"],
            "exit_date": dates[exit_idx], "exit_price": exit_price, "open": is_open,
            "stop": cup["stop"], "buy_point": cup["buy_point"],
            "left_rim_date": dates[cup["left_rim"]].strftime("%Y-%m-%d"),
            "tranches": [{
                "fraction": round(t["fraction"], 6),
                "exit_date": None if t["exit_idx"] is None else dates[t["exit_idx"]].strftime("%Y-%m-%d"),
                "exit_price": None if t["exit_price"] is None else round(t["exit_price"], 2),
                "reason": t["reason"],
            } for t in tranches],
        })
        busy_until = last if is_open else exit_idx
    return trades


def evaluate(symbol: str) -> dict:
    ohlc, dates = monthly_ohlc(symbol)
    return {"ohlc": ohlc, "dates": dates, "cups": detect_cups(ohlc)}


def backtest(symbol: str, capital: float, ev: dict | None = None) -> dict:
    """One backtest per selling ladder (all money hypothetical)."""
    import pandas as pd

    ev = ev or evaluate(symbol)
    bars = pd.DataFrame({"date": ev["dates"], "close": ev["ohlc"]["close"]})
    times = bars["date"].dt.strftime("%Y-%m-%d").to_list()
    out = {}
    for mode in MODES:
        trades = trades_for_mode(ev["cups"], ev["ohlc"], ev["dates"], mode)
        summary = bt.summarize(trades, bars, capital)
        equity = summary.pop("equity")
        rows = bt.trade_rows(trades)
        for r in rows:
            for k in ("entry_price", "exit_price", "stop", "buy_point"):
                r[k] = round(r[k], 2)
        out[mode] = {
            "summary": summary,
            "trades": rows,
            "equity": [{"time": t, "value": round(v, 2)} for t, v in zip(times, equity)],
            "buy_hold": [{"time": t, "value": round(v, 2)} for t, v in zip(times, bt.buy_hold_curve(bars, capital))],
        }
    return out


def ladder_levels(entry: float, stop: float) -> dict:
    """The plain price levels each mode works with (shown only after confirmation)."""
    return {
        "income": {"sells": [{"gain": g, "fraction": f, "price": round(entry * (1 + g), 2)} for g, f in SELLS["income"]],
                   "stop": round(stop, 2), "stop_rule": "the stop stays fixed at entry and is never raised"},
        "wealth": {"sells": [{"gain": g, "fraction": f, "price": round(entry * (1 + g), 2)} for g, f in SELLS["wealth"]],
                   "stop": round(stop, 2),
                   "stop_rule": "the stop rises at each +10% milestone, first to +10% and then to the milestone minus 10%"},
        "trail": {"sells": [], "stop": round(stop, 2),
                  "stop_rule": "the stop rises exactly as in Wealth, and the whole position rides until it is hit"},
    }


def current_status(symbol: str, ev: dict | None = None) -> dict:
    """The most recently formed complete setup (or NONE). Detection only: this is a
    POSSIBLE formation for a human to review, never a buy signal."""
    ev = ev or evaluate(symbol)
    if not ev["cups"]:
        return {"status": "NONE", "as_of": ev["dates"][-1].strftime("%Y-%m-%d") if ev["dates"] else None}
    cup = max(ev["cups"], key=lambda k: k["regain"])
    d, h, lo = ev["dates"], ev["ohlc"]["high"], ev["ohlc"]["low"]
    fmt = lambda i: d[i].strftime("%Y-%m-%d")  # noqa: E731
    e = find_entry(cup, h)
    return {
        "status": "POSSIBLE",
        "as_of": fmt(len(d) - 1),
        "cup": {
            "left_rim_date": fmt(cup["left_rim"]), "left_rim_high": round(h[cup["left_rim"]], 2),
            "bottom_date": fmt(cup["bottom"]), "bottom_low": round(lo[cup["bottom"]], 2),
            "right_rim_date": fmt(cup["right_rim"]), "right_rim_high": round(h[cup["right_rim"]], 2),
            "handle_start": fmt(cup["handle_start"]), "handle_end": fmt(cup["handle_end"]),
            "handle_low": round(cup["handle_low"], 2),
            "months": cup["right_rim"] - cup["left_rim"], "depth": round(cup["depth"], 4),
            "bottom_dwell": round(cup["dwell"], 4),
        },
        # levels are computed here but the API only reveals them after a human confirms
        "levels": {
            "buy_point": round(cup["buy_point"], 2),
            "entry": round(cup["entry_level"], 2),
            "stop": round(cup["stop"], 2),
            "entry_triggered": e is not None,
            "entry_date": fmt(e) if e is not None else None,
            "ladders": ladder_levels(cup["entry_level"], cup["stop"]),
        },
    }
