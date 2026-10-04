"""Verify app/systems/cup_pattern.py (System 2, Cup & Handle).

1. Real data: an independent from-scratch detector agrees with production on all five
   stocks (zero cups at the notes' strict thresholds, the expected result) AND under
   loosened test thresholds passed in temporarily, so real cups appear and both must find
   exactly the same ones. The module file is never edited.
2. A hand-built 91-month series: a first right rim whose handle is too deep (rejected),
   a second that qualifies, the buy point / entry / stop, the pending stop filling at the
   trigger level (not the month's high), and no lookahead (truncated data finds nothing early).
3. Each selling ladder walked through numbers worked out on paper, including the stop
   coming first inside a month, the stop never rising in Income, the +10% -> +10% first
   step, and the ladder continuing past +100%.
4. Backtest ordering: overlapping cups walked in ENTRY order, one position at a time,
   tranches blended correctly.

Trap from v1: the simulators start at entry_idx + 1, so every ladder fixture has a
dummy entry month at index 0 (otherwise every milestone shifts by one month).

Run:  python scripts/verify_cup_pattern.py
"""
import math
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.stocks import TICKERS  # noqa: E402
from app.systems import cup_pattern as cp  # noqa: E402

failures: list[str] = []
checks = 0


def check(cond, msg):
    global checks
    checks += 1
    if not cond:
        failures.append(msg)


STRICT = dict(window=3, symmetry=0.08, min_months=60, depth=(0.12, 0.50), quart=0.25, dwell=0.20, handle=(1, 6), retrace=1 / 3)


# ---------------------------------------------------------------------------
# Independent reference detector (plain loops, written separately from production)
# ---------------------------------------------------------------------------
def ref_detect(H, L, C, p):
    w = p["window"]
    rims = [i for i in range(w, len(H) - w) if all(H[j] <= H[i] for j in range(i - w, i + w + 1))]
    found, used = [], set()
    for a in rims:
        for z in rims:
            if z <= a or z - a < p["min_months"]:
                continue
            if abs(H[z] / H[a] - 1) > p["symmetry"]:
                continue
            bottom = a + 1
            for k in range(a + 1, z):
                if L[k] < L[bottom]:
                    bottom = k
            depth = 1 - L[bottom] / H[a]
            if depth < p["depth"][0] or depth > p["depth"][1]:
                continue
            cutoff = L[bottom] + p["quart"] * (H[a] - L[bottom])
            near = 0
            for k in range(a, z + 1):
                near += C[k] <= cutoff
            if near / (z - a + 1) < p["dwell"]:
                continue
            regain = next((x for x in range(z + 1, len(H)) if H[x] > H[z]), None)
            if regain is None:
                continue
            n_handle = regain - z - 1
            if n_handle < p["handle"][0] or n_handle > p["handle"][1]:
                continue
            if H[z] - min(L[z + 1:regain]) >= p["retrace"] * (H[a] - L[bottom]):
                continue
            if (z, regain) in used:
                break
            used.add((z, regain))
            bp = max(H[z + 1:regain])
            found.append((a, bottom, z, z + 1, regain - 1, regain, round(bp, 6), max(regain, z + w) + 1))
            break
    return found


def prod_tuple(cups):
    return [(c["left_rim"], c["bottom"], c["right_rim"], c["handle_start"], c["handle_end"], c["regain"],
             round(c["buy_point"], 6), c["first_entry_month"]) for c in cups]


def with_params(p, fn):
    """Run fn with the module's thresholds temporarily set to p (in memory only)."""
    names = dict(RIM_WINDOW="window", RIM_SYMMETRY="symmetry", MIN_CUP_MONTHS="min_months",
                 BOTTOM_QUARTILE="quart", BOTTOM_DWELL_FRAC="dwell", HANDLE_MAX_RETRACE="retrace")
    saved = {k: getattr(cp, k) for k in list(names) + ["DEPTH_MIN", "DEPTH_MAX", "HANDLE_MIN_MONTHS", "HANDLE_MAX_MONTHS"]}
    try:
        for k, v in names.items():
            setattr(cp, k, p[v])
        cp.DEPTH_MIN, cp.DEPTH_MAX = p["depth"]
        cp.HANDLE_MIN_MONTHS, cp.HANDLE_MAX_MONTHS = p["handle"]
        return fn()
    finally:
        for k, v in saved.items():
            setattr(cp, k, v)


def real_data():
    print("1. Real data: production vs independent detector")
    loose = dict(STRICT, symmetry=4.0, min_months=24, depth=(0.05, 0.95), dwell=0.0, handle=(1, 12), retrace=1.0)
    total_loose = 0
    for sym in TICKERS:
        ohlc, dates = cp.monthly_ohlc(sym)
        H, L, C = ohlc["high"], ohlc["low"], ohlc["close"]
        prod = cp.detect_cups(ohlc)
        check(prod_tuple(prod) == ref_detect(H, L, C, STRICT), f"{sym}: strict detection differs from reference")
        check(prod == [], f"{sym}: expected zero cups at the strict thresholds, found {len(prod)}")
        check(cp.current_status(sym)["status"] == "NONE", f"{sym}: status should be NONE")
        rims = cp.local_highs(H)
        ref_rims = [i for i in range(3, len(H) - 3) if all(H[j] <= H[i] for j in range(i - 3, i + 4))]
        check(rims == ref_rims, f"{sym}: local highs differ")
        within = [(a, b) for a in rims for b in rims if b - a >= 60 and abs(H[b] / H[a] - 1) <= 0.08]
        check(within == [], f"{sym}: a 60-month rim pair within 8% exists, so zero cups is not explained by symmetry")
        loose_prod = with_params(loose, lambda: cp.detect_cups(ohlc))
        loose_ref = ref_detect(H, L, C, loose)
        check(prod_tuple(loose_prod) == loose_ref, f"{sym}: loosened detection differs from reference")
        total_loose += len(loose_ref)
        print(f"   {sym:<14} strict: 0 cups (no 60-month rim pair within 8%)   loosened test thresholds: {len(loose_ref)} cups, identical")
    check(total_loose > 0, "loosened thresholds should produce some cups to compare")
    check(cp.RIM_SYMMETRY == 0.08 and cp.MIN_CUP_MONTHS == 60, "module thresholds were not restored")


# ---------------------------------------------------------------------------
# Hand-built 91-month series
# ---------------------------------------------------------------------------
def synthetic():
    """Month : high (low = high - 3 unless stated, close = high - 1)
       0-4 rising to 98; 5 = LEFT RIM 100; 6-19 fall to 70; 20-44 a long flat bottom near 68
       (low 65 at month 30); 45-65 rise; 66 = right rim #1 at 99 with a TOO-DEEP handle
       (lows 92, 86, 85: retrace 14 >= 1/3 x depth 35 = 11.67); 70 regains 99;
       72 = right rim #2 at 101; handle 73-75 (highs 99.5, 98.5, 99; lows 97, 95.5, 96);
       76 regains 101 (high 102); 77 high 104 > trigger 103.48; 78-90 drift near 105."""
    H = [90, 92, 94, 96, 98, 100]
    H += [97 - (97 - 70) * k / 13 for k in range(14)]                 # 6-19
    H += [68 + 0.01 * k for k in range(25)]                           # 20-44 (strictly rising: no local highs)
    H += [70 + (98.5 - 70) * k / 20 for k in range(21)]               # 45-65
    H += [99, 95, 90, 88, 100, 100.5, 101, 99.5, 98.5, 99, 102, 104]  # 66-77
    H += [104.5 + 0.05 * k for k in range(13)]                        # 78-90
    L = [x - 3 for x in H]
    C = [x - 1 for x in H]
    L[30] = 64.5   # strictly below every other low (month 20's low is 65), so the bottom is unique
    for m, v in ((67, 92), (68, 86), (69, 85), (73, 97), (74, 95.5), (75, 96), (77, 100)):
        L[m] = v
    O = list(C)
    return {"open": O, "high": H, "low": L, "close": C}


def synthetic_checks():
    print("2. Hand-built series")
    s = synthetic()
    check(len(s["high"]) == 91, "fixture length")
    cups = cp.detect_cups(s)
    check(len(cups) == 1, f"expected exactly one cup, got {len(cups)}")
    if not cups:
        return
    c = cups[0]
    check((c["left_rim"], c["right_rim"]) == (5, 72), f"rims {c['left_rim']}, {c['right_rim']} (66 must be rejected: deep handle)")
    check(c["bottom"] == 30 and math.isclose(c["depth"], 0.355), f"bottom {c['bottom']} depth {c['depth']}")
    check((c["handle_start"], c["handle_end"], c["regain"]) == (73, 75, 76), "handle should be months 73-75, regained in 76")
    check(c["buy_point"] == 99.5, f"buy point {c['buy_point']} should be the handle's highest high 99.5")
    check(math.isclose(c["entry_level"], 103.48) and math.isclose(c["stop"], 75.62), "entry 99.5x1.04, stop 99.5x0.76")
    check(c["first_entry_month"] == 77, "the stop-buy may fill only from month 77")
    check(prod_tuple(cups) == ref_detect(s["high"], s["low"], s["close"], STRICT), "synthetic: reference disagrees")
    e = cp.find_entry(c, s["high"])
    check(e == 77, f"entry month {e}")
    trades = cp.trades_for_mode(cups, s, list(pd.date_range("2010-01-31", periods=91, freq="ME")), "trail")
    check(len(trades) == 1 and math.isclose(trades[0]["entry_price"], 103.48),
          "entry price must be the trigger level 103.48, not month 77's high 104")
    check(trades[0]["open"], "with no stop or milestone hit the position stays open to the end")
    # no lookahead: with data only up to month 75 the handle is unfinished; up to 76 the cup
    # exists but nothing can fill yet
    cut = lambda n: {k: v[:n] for k, v in s.items()}  # noqa: E731
    check(cp.detect_cups(cut(76)) == [], "a cup must not be known before its handle has ended")
    c76 = cp.detect_cups(cut(77))
    check(len(c76) == 1 and cp.find_entry(c76[0], cut(77)["high"]) is None, "no entry until month 77 exists")
    # the 1/3 retrace rule really rejects: same series with a shallow first handle finds right rim 66
    s2 = synthetic()
    for m in (67, 68, 69):
        s2["low"][m] = 93
    c2 = cp.detect_cups(s2)
    check(c2 and c2[0]["right_rim"] == 66, "with a shallow handle, right rim 66 should qualify")
    print("   done")


# ---------------------------------------------------------------------------
# Selling ladders
# ---------------------------------------------------------------------------
def months(rows):
    """rows of (high, low); index 0 is the dummy ENTRY month (simulators start at 1)."""
    rows = [(100, 100)] + rows
    return {"open": [100] * len(rows), "high": [r[0] for r in rows], "low": [r[1] for r in rows],
            "close": [(r[0] + r[1]) / 2 for r in rows]}


def run(mode, rows, entry=100.0, stop=76.0):
    o = months(rows)
    t = cp.simulate(mode, 0, entry, stop, o)
    return t, cp.blend(t, entry, o["close"][-1])


def brief(t):
    """Tranches as (fraction, month, price) with float noise rounded away (100 x 1.1 = 110.00000000000001)."""
    return [(round(x["fraction"], 4), x["exit_idx"], None if x["exit_price"] is None else round(x["exit_price"], 6)) for x in t]


def ladders():
    print("3. Selling ladders")
    # Income: 1/3 at 110, 1/3 at 120, last 1/3 stopped at the ORIGINAL 76 (never raised).
    t, (value, is_open) = run("income", [(111, 101), (121, 105), (130, 90), (100, 75)])
    check(brief(t) == [(0.3333, 1, 110.0), (0.3333, 2, 120.0), (0.3333, 4, 76.0)], f"income tranches {t}")
    check(math.isclose(value, (110 + 120 + 76) / 3) and not is_open, f"income blended {value}")
    # Wealth: +10% -> stop 110; sell at 120; +30% -> stop 120; sell at 140, +40% -> stop 130; month 5 low 129 -> out at 130
    t, (value, is_open) = run("wealth", [(111, 101), (121, 111), (131, 115), (141, 125), (135, 129)])
    check(brief(t) == [(0.3333, 2, 120.0), (0.3333, 4, 140.0), (0.3333, 5, 130.0)], f"wealth tranches {t}")
    check(math.isclose(value, (120 + 140 + 130) / 3), f"wealth blended {value}")
    # Trail: same path, no partial sells: everything out at the 130 stop
    t, (value, _) = run("trail", [(111, 101), (121, 111), (131, 115), (141, 125), (135, 129)])
    check(brief(t) == [(1.0, 5, 130.0)], f"trail {t}")
    # First milestone raises the stop to +10% itself (not to breakeven)
    t, _ = run("trail", [(111, 101), (109, 109.5)])
    check(brief(t) == [(1.0, 2, 110.0)], f"+10% should lift the stop to 110: {t}")
    t, _ = run("trail", [(111, 101), (109, 111)])
    check(t[-1]["reason"] == "open", "a low above 110 must not stop out")
    # Ladder continues past +100%: reaching +110% (milestone 11) lifts the stop to +100%
    check([cp.trailing_stop_pct(k) for k in (0, 1, 2, 3, 4, 11)] == [None, 0.10, 0.10, 0.20, 0.30, 1.0], "stop schedule")
    t, _ = run("trail", [(211, 150), (205, 199)])
    check(brief(t) == [(1.0, 2, 200.0)], f"after +110% the stop should be 200: {t}")
    # Inside one month the stop comes first: a month touching both 120 and the stop sells nothing
    t, _ = run("income", [(125, 70)])
    check(len(t) == 1 and t[0]["reason"] == "stop" and t[0]["exit_price"] == 76.0, f"stop-first: {t}")
    # A stop raised by this month's high only applies from next month
    t, _ = run("trail", [(121, 105)])
    check(t[-1]["reason"] == "open", "month 1's own low (105) must not hit the stop it just raised (110)")
    # The entry month itself is never evaluated (simulators start at entry_idx + 1)
    o = months([(101, 99)])
    o["high"][0], o["low"][0] = 300, 1
    t = cp.simulate("income", 0, 100.0, 76.0, o)
    check(t[-1]["reason"] == "open" and len(t) == 1, "the entry month's high/low must be ignored")
    # Income's last third stays open if never stopped; blend values it at the last close
    t, (value, is_open) = run("income", [(111, 101), (121, 105), (118, 112)])
    check(is_open and math.isclose(value, (110 + 120 + 115) / 3), f"open blend {value}")
    print("   done")


def ordering():
    print("4. Backtest ordering and one position at a time")
    # Cup A has the EARLIER left rim but its entry triggers later; B triggers first and is still
    # open when A triggers, so A must be skipped. C triggers after B is stopped out.
    o = months([(100, 99)] * 3 + [(106, 100)] + [(105, 101)] * 2 + [(108, 102)] + [(103, 70)] + [(100, 95)] * 2 + [(112, 101)] + [(111, 102)])
    n = len(o["high"])
    dates = list(pd.date_range("2015-01-31", periods=n, freq="ME"))
    mk = lambda li, lvl, first: {"left_rim": li, "buy_point": lvl / 1.04, "entry_level": lvl, "stop": lvl / 1.04 * 0.76,  # noqa: E731
                                 "first_entry_month": first}
    A, B, C = mk(0, 107.0, 1), mk(1, 105.0, 1), mk(2, 110.0, 9)
    trades = cp.trades_for_mode([A, B, C], o, dates, "trail")
    check([t["left_rim_date"] for t in trades] == [dates[1].strftime("%Y-%m-%d"), dates[2].strftime("%Y-%m-%d")],
          f"expected B then C (A skipped while B is held): {[t['left_rim_date'] for t in trades]}")
    check(trades[0]["entry_date"] == dates[4] and trades[0]["exit_date"] == dates[8],
          "B enters in month 4 (high 106 > 105) and is stopped in month 8")
    check(all(trades[i]["exit_date"] < trades[i + 1]["entry_date"] for i in range(len(trades) - 1)), "trades overlap")
    print("   done")


def main():
    real_data()
    synthetic_checks()
    ladders()
    ordering()
    print()
    if failures:
        print(f"FAILURES ({len(failures)}):")
        for f in failures:
            print("  ", f)
        return 1
    print(f"All {checks} checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
