"""Verify app/systems/value_buy.py (System 3, Value Buy).

1. Independent from-scratch reimplementation (plain Python: monthly RSI, the as-of
   month join, the weekly arm/trigger/expire/re-arm/bracket loop, the swing target)
   compared with production on all five stocks: states, exit reasons and trades
   must match exactly.
2. No lookahead: every week only sees a COMPLETED month that ended on or before it.
3. Hand-built scenarios fed straight into run_weekly_state_machine() with chosen
   prices and context: happy path, 2-week expiry (and a trigger in week 2), re-arm,
   stop exit, one position at a time, context required; plus target-below-entry,
   stop-and-target in one week, and the swing-confirmation rule.
4. Invariants every real trade must satisfy, and the Bajaj Auto zero-trades result.

Fixture trap noted from v1: a "red" week must really have close < open, and a
signal week must really be green. Every fixture week states its open and close.

Run:  python scripts/verify_value_buy.py
"""
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from app import prices  # noqa: E402
from app.stocks import TICKERS  # noqa: E402
from app.systems import value_buy as vb  # noqa: E402
from verify_indicators import ref_rsi  # noqa: E402

failures: list[str] = []
checks = 0


def check(cond, msg):
    global checks
    checks += 1
    if not cond:
        failures.append(msg)


# ---------------------------------------------------------------------------
# Independent reference
# ---------------------------------------------------------------------------
def ref_value_buy(symbol, lookback=20):
    wk = prices.load_completed_prices(symbol, "weekly")
    mo = prices.load_completed_prices(symbol, "monthly")
    ratio = [a / c for a, c in zip(wk["adj_close"], wk["close"])]
    O = [x * r for x, r in zip(wk["open"], ratio)]
    H = [x * r for x, r in zip(wk["high"], ratio)]
    L = [x * r for x, r in zip(wk["low"], ratio)]
    C = list(wk["adj_close"])
    mrsi = ref_rsi(list(mo["adj_close"]), 14)
    mdates = list(mo["date"])

    ctx = []
    for w in wk["date"]:
        k = None
        for j, d in enumerate(mdates):        # last month-end on or before the week
            if d <= w:
                k = j
        ok = (k is not None and k >= 1 and mrsi[k] is not None and mrsi[k - 1] is not None
              and 38 <= mrsi[k] <= 45 and mrsi[k] > mrsi[k - 1])
        ctx.append(ok)

    def target_at(i):
        cands = [H[j] for j in range(1, i - 1) if j >= i - lookback and H[j] > H[j - 1] and H[j] > H[j + 1]]
        return max(cands) if cands else None

    states, reasons, trades = [], [], []
    mode = "flat"            # flat / armed / long
    sig = lvl = stp = tgt = ent = None
    entry_i = sig_i = None
    for i in range(len(C)):
        if mode == "long":
            if L[i] <= stp:
                trades.append((sig_i, entry_i, i, ent, stp, tgt, stp, "stop"))
                states.append("SELL"); reasons.append("stop"); mode = "flat"; continue
            if H[i] >= tgt:
                trades.append((sig_i, entry_i, i, ent, stp, tgt, tgt, "target"))
                states.append("SELL"); reasons.append("target"); mode = "flat"; continue
            states.append("HOLD"); reasons.append(None); continue
        if mode == "armed" and sig < i <= sig + 2 and H[i] > lvl:
            t = target_at(i)
            if t is not None and t > lvl:
                ent, tgt, entry_i, sig_i = lvl, t, i, sig
                mode = "long"; states.append("BUY"); reasons.append(None); continue
        if ctx[i] and C[i] > O[i]:
            mode, sig, lvl, stp = "armed", i, H[i], L[i]
        elif mode == "armed" and i >= sig + 2:
            mode = "flat"
        states.append("ARMED" if mode == "armed" else "NEUTRAL"); reasons.append(None)
    if mode == "long":
        trades.append((sig_i, entry_i, None, ent, stp, tgt, None, None))
    return states, reasons, trades, ctx, (O, H, L, C)


def real_data():
    print("1+2+4. Real data: production vs reference, no lookahead, invariants")
    cutoff = prices.downloaded_on()
    for sym in TICKERS:
        ev = vb.evaluate(sym)
        st, rs, tr, ctx, (O, H, L, C) = ref_value_buy(sym)
        got_states = [r["state"] for r in ev["rows"]]
        got_reasons = [r["exit_reason"] for r in ev["rows"]]
        check(got_states == st, f"{sym}: states differ from reference")
        check(got_reasons == rs, f"{sym}: exit reasons differ from reference")
        check(ev["context"]["active"].to_list() == ctx, f"{sym}: context differs from reference")
        got_tr = [(t["signal_idx"], t["entry_idx"], t["exit_idx"], t["entry"], t["stop"], t["target"],
                   t["exit_price"], t["exit_reason"]) for t in ev["trades"]]
        check(got_tr == tr, f"{sym}: trades differ from reference")

        # no lookahead in the month join
        weeks, months = ev["weekly"]["date"], ev["context"]["month"]
        for w, m in zip(weeks, months):
            if isinstance(m, float) or m is None or (hasattr(m, "year") is False):
                continue
            if m != m:   # NaT
                continue
            check(m <= w and m.date() < cutoff, f"{sym}: week {w:%Y-%m-%d} sees month {m:%Y-%m-%d}")

        # invariants
        for (s_i, e_i, x_i, ent, stp, tgt, xp, why) in tr:
            check(C[s_i] > O[s_i] and ctx[s_i], f"{sym}: signal week {s_i} not a green week in context")
            check(ent == H[s_i] and stp == L[s_i], f"{sym}: entry/stop not the signal candle's high/low")
            check(s_i < e_i <= s_i + 2, f"{sym}: entry {e_i} outside the 2-week window after signal {s_i}")
            check(H[e_i] > ent, f"{sym}: entry week never traded above the stop-buy")
            check(stp < ent < tgt, f"{sym}: not stop < entry < target ({stp}, {ent}, {tgt})")
            if why == "stop":
                check(xp == stp and L[x_i] <= stp, f"{sym}: stop exit wrong")
            elif why == "target":
                check(xp == tgt and H[x_i] >= tgt and L[x_i] > stp, f"{sym}: target exit wrong")
        spans = [(t[1], t[2] if t[2] is not None else 10**9) for t in tr]
        check(all(spans[k][1] < spans[k + 1][0] for k in range(len(spans) - 1)), f"{sym}: overlapping positions")
        print(f"   {sym:<14} {len(tr)} trades, {sum(ctx)} context-active weeks: matches reference")

    check(len(vb.evaluate("BAJAJ-AUTO.NS")["trades"]) == 0, "Bajaj Auto should have zero Value Buy trades")
    ctx = vb.monthly_context("BAJAJ-AUTO.NS")
    in_zone = ctx[(ctx["rsi"] >= 38) & (ctx["rsi"] <= 45)]
    check(len(in_zone) > 0 and not in_zone["active"].any(),
          "Bajaj Auto: monthly RSI should touch 38-45 only while falling")
    print(f"   Bajaj Auto: months in the 38-45 zone: {len(in_zone)}, of which rising: {int(in_zone['active'].sum())}")


# ---------------------------------------------------------------------------
# Hand-built scenarios
# ---------------------------------------------------------------------------
# Base weeks (open, high, low, close). Week 1 is a swing high at 120 (above weeks 0 and 2).
BASE = [
    (100, 105, 95, 100),   # 0
    (100, 120, 98, 110),   # 1  swing high 120
    (110, 112, 100, 102),  # 2  red
    (102, 104, 96, 98),    # 3  red
    (98, 103, 97, 102),    # 4  GREEN: the signal candle when context is on (level 103, stop 97)
]


def run(weeks, context):
    o, h, lo, c = (list(x) for x in zip(*weeks))
    for i, (a, _, _, z) in enumerate(weeks):
        if context[i] and z > a:
            pass  # green weeks in context are signal candles; that is intended where used
    return vb.run_weekly_state_machine({"open": o, "high": h, "low": lo, "close": c}, context)


def ctx_on(n, on):
    return [i in on for i in range(n)]


def scenario(name, weeks, on, want_states, want_trades=None):
    rows, trades = run(weeks, ctx_on(len(weeks), on))
    got = [r["state"] for r in rows]
    check(got == want_states, f"scenario '{name}': {got} != {want_states}")
    if want_trades is not None:
        brief = [(t["entry_idx"], t["entry"], t["stop"], t["target"], t["exit_idx"], t["exit_price"], t["exit_reason"]) for t in trades]
        check(brief == want_trades, f"scenario '{name}': trades {brief} != {want_trades}")
    return rows, trades


def scenarios():
    print("3. Hand-built scenarios")
    N = "NEUTRAL"
    # 1. Happy path: signal week 4 arms at 103; week 5 trades above -> BUY at 103 (not week 5's
    #    own high); target = swing high 120; week 7 reaches 120 -> SELL at the target.
    weeks = BASE + [(103, 106, 101, 105), (105, 110, 101, 108), (108, 121, 106, 119)]
    _, tr = scenario("happy path", weeks, {4}, [N, N, N, N, "ARMED", "BUY", "HOLD", "SELL"],
                     [(5, 103, 97, 120, 7, 120, "target")])
    rr = (120 - 103) / (103 - 97)
    check(math.isclose(vb._risk_reward(103, 97, 120)["ratio"], rr), "risk-reward should be (120-103)/(103-97)")

    # 2. Expiry: no week trades above 103 within 2 weeks -> setup gone; a later rise above 103 does nothing.
    weeks = BASE + [(101, 102.5, 99, 100), (100, 102.9, 99, 99.5), (99.5, 110, 99, 109)]
    scenario("2-week expiry", weeks, {4}, [N, N, N, N, "ARMED", "ARMED", N, N], [])
    #    ...but a trigger in the SECOND week still counts.
    weeks = BASE + [(101, 102.5, 99, 100), (100, 104, 99, 99.5)]
    scenario("trigger in week 2", weeks, {4}, [N, N, N, N, "ARMED", "ARMED", "BUY"], [(6, 103, 97, 120, None, None, None)])

    # 3. Re-arm: week 5 is a new green signal (high 101.5, low 98.5) -> re-arms lower and restarts 2 weeks.
    #    Week 7 trades above 101.5 (but not 103, and after the old expiry) -> BUY at 101.5, stop 98.5.
    weeks = BASE + [(99, 101.5, 98.5, 101), (101, 101, 99, 100), (100, 102, 99.5, 101.8)]
    scenario("re-arm", weeks, {4, 5}, [N, N, N, N, "ARMED", "ARMED", "ARMED", "BUY"],
             [(7, 101.5, 98.5, 120, None, None, None)])

    # 4. Stop exit: after entry, a week trades down to the signal low 97 -> SELL at 97 (fixed, never trails).
    weeks = BASE + [(103, 106, 101, 105), (105, 109, 104, 108), (104, 105, 96.5, 98)]
    scenario("stop exit", weeks, {4}, [N, N, N, N, "ARMED", "BUY", "HOLD", "SELL"],
             [(5, 103, 97, 120, 7, 97, "stop")])
    #    A week that touches BOTH stop and target counts as the stop (cautious).
    weeks = BASE + [(103, 106, 101, 105), (105, 125, 96, 110)]
    scenario("stop and target same week", weeks, {4}, [N, N, N, N, "ARMED", "BUY", "SELL"],
             [(5, 103, 97, 120, 6, 97, "stop")])

    # 5. One position at a time: while holding, a green week in context (would be a signal if flat)
    #    and a week above its high do NOT add a position.
    weeks = BASE + [(103, 106, 101, 105), (104, 108, 103, 107), (107, 110, 106, 109)]
    scenario("one position at a time", weeks, {4, 6}, [N, N, N, N, "ARMED", "BUY", "HOLD", "HOLD"],
             [(5, 103, 97, 120, None, None, None)])

    # 6. Context required: the same prices with context off produce nothing.
    weeks = BASE + [(103, 106, 101, 105), (105, 110, 101, 108), (108, 121, 106, 119)]
    scenario("context required", weeks, set(), [N] * 8, [])
    #    ...and the context rule itself: 38-45 AND rising; falling into the zone does not count.
    for rsi, prev, want in ((44, 50, False), (43, 44, False), (44, 43, True), (38, 37, True), (45, 44.9, True),
                            (45.01, 44, False), (37.99, 30, False), (40, 40, False), (40, float("nan"), False)):
        check(vb.is_context_active(rsi, prev) == want, f"context({rsi}, prev {prev}) should be {want}")

    # Extra: no swing high above the entry -> the entry is skipped and the setup stays armed, then expires.
    low = [(100, 100, 95, 98), (98, 102, 96, 99), (99, 101, 97, 98), (98, 100, 96, 97), (97, 103, 96.5, 102),
           (102, 106, 101, 104), (104, 107, 102, 103), (103, 108, 102, 107)]
    scenario("target not above entry", low, {4}, [N, N, N, N, "ARMED", "ARMED", N, N], [])

    # Extra: swing confirmation. A swing high one week before the trigger is not yet confirmed.
    hs = [1, 5, 1, 9, 1, 0]
    check(vb.swing_target(hs, 5) == 9, "swing at i-2 (confirmed) should be usable")
    check(vb.swing_target(hs, 4) == 5, "swing at i-1 is unconfirmed and must be ignored")
    check(vb.swing_target([1, 2, 3, 4, 5], 5) is None, "a steady rise has no swing high")
    check(vb.swing_target([1, 9, 1] + [1] * 30, 33) is None, "a swing older than 20 weeks is outside the lookback")
    print("   done")


def main():
    real_data()
    scenarios()
    print()
    if failures:
        print(f"FAILURES ({len(failures)}):")
        for f in failures[:40]:
            print("  ", f)
        return 1
    print(f"All {checks} checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
