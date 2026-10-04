"""Verify app/systems/backtest.py and the System 1 backtest / portfolio built on it.

1. Independent from-scratch reimplementation (plain Python: trades derived from the
   state list, compounding, drawdown, losing streak, buy-and-hold) compared with
   production on all five stocks and the portfolio.
2. Invariants: equity always positive, flat outside trades, final equity equals
   capital x product of (1 + trade return), portfolio equals the sum of its parts,
   capital scales linearly, results identical whatever the capital.
3. Hand-built scenarios with numbers worked out on paper.

Run:  python scripts/verify_backtest.py
"""
import math
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.stocks import TICKERS  # noqa: E402
from app.systems import backtest as bt  # noqa: E402
from app.systems import trend_following as s1  # noqa: E402

failures: list[str] = []
checks = 0
REL = 1e-9  # relative tolerance: independent code may multiply in a different order


def check(cond, msg):
    global checks
    checks += 1
    if not cond:
        failures.append(msg)


def close_enough(a, b):
    return abs(a - b) <= REL * max(1.0, abs(a), abs(b))


# ---------------------------------------------------------------------------
# Independent reference
# ---------------------------------------------------------------------------
def ref_backtest(dates, states, closes, capital):
    """dates/states/closes for the evaluable weeks only (state never None)."""
    trades, entry = [], None
    for i, st in enumerate(states):
        if st == "BUY":
            entry = i
        elif st == "SELL":
            trades.append((entry, i, False))
            entry = None
    if entry is not None:
        trades.append((entry, len(states) - 1, True))

    equity, cash, holding_from = [], capital, None
    starts = {e: (e, x) for e, x, _ in trades}
    active = None
    for i in range(len(closes)):
        if active is None and i in starts:
            active = starts[i]
            holding_from = cash
        if active is not None:
            e, x = active
            value = holding_from * closes[i] / closes[e]
            if i == x:
                cash = value
                active = None
            equity.append(value)
        else:
            equity.append(cash)

    peak, dd = 0.0, 0.0
    for v in equity:
        peak = max(peak, v)
        dd = min(dd, (v - peak) / peak)

    streak = best = 0
    for e, x, is_open in trades:
        if is_open:
            continue
        streak = streak + 1 if closes[x] < closes[e] else 0
        best = max(best, streak)

    closed = [(e, x) for e, x, o in trades if not o]
    wins = sum(1 for e, x in closed if closes[x] > closes[e])
    return {
        "equity": equity,
        "final": equity[-1],
        "total_return": equity[-1] / capital - 1,
        "buy_hold_return": closes[-1] / closes[0] - 1,
        "max_drawdown": dd,
        "streak": best,
        "closed": len(closed),
        "wins": wins,
        "open": any(o for _, _, o in trades),
        "trades": trades,
    }


def real_data():
    print("1+2. Real data: production vs reference, and invariants")
    capital = 100000.0
    for sym in TICKERS:
        rows = s1.evaluate(sym)
        valid = rows[rows["state"].notna()]
        ref = ref_backtest(valid["date"].to_list(), valid["state"].to_list(), valid["close"].to_list(), capital)
        res = s1.backtest(sym, capital)
        sm = res["summary"]
        eq = [p["value"] for p in res["equity"]]
        raw = s1._backtest_raw(sym, capital)["equity"]

        check(len(raw) == len(ref["equity"]), f"{sym}: equity length differs")
        worst = max(abs(a - b) / max(1, abs(b)) for a, b in zip(raw, ref["equity"]))
        check(worst <= REL, f"{sym}: equity curve differs from reference (rel {worst:.2e})")
        check(all(abs(a - round(b, 2)) < 1e-9 for a, b in zip(eq, raw)), f"{sym}: API equity is not the rounded raw curve")
        for key, rkey in (("total_return", "total_return"), ("buy_hold_return", "buy_hold_return"),
                          ("max_drawdown", "max_drawdown"), ("final_equity", "final")):
            check(close_enough(sm[key], ref[rkey]), f"{sym}: {key} {sm[key]} vs reference {ref[rkey]}")
        check(sm["longest_losing_streak"] == ref["streak"], f"{sym}: losing streak {sm['longest_losing_streak']} vs {ref['streak']}")
        check(sm["closed_trades"] == ref["closed"] and sm["wins"] == ref["wins"], f"{sym}: trade counts differ")
        check((sm["open_trade"] is not None) == ref["open"], f"{sym}: open trade flag differs")

        # invariants
        check(all(v > 0 for v in raw), f"{sym}: equity not always positive")
        product = capital
        for t in res["trades"]:
            product *= 1 + t["return"]
            check((t["return"] > 0) == (t["exit_price"] > t["entry_price"]), f"{sym}: return sign wrong")
        check(close_enough(product, sm["final_equity"]), f"{sym}: final equity != capital x product(1+r)")
        check(sm["max_drawdown"] <= 0, f"{sym}: drawdown positive")
        in_trade = set()
        index = {p["time"]: i for i, p in enumerate(res["equity"])}
        for t in res["trades"]:
            in_trade.update(range(index[t["entry_date"]] + 1, index[t["exit_date"]] + 1))
        flat_ok = all(raw[i] == raw[i - 1] for i in range(1, len(raw)) if i not in in_trade)
        check(flat_ok, f"{sym}: equity moved while flat")
        # capital scales linearly; percentages do not depend on capital
        big = s1.backtest(sym, 12345678.0)["summary"]
        check(close_enough(big["total_return"], sm["total_return"]), f"{sym}: return depends on capital")
        check(close_enough(big["final_equity"] / 12345678.0, sm["final_equity"] / capital), f"{sym}: equity not linear in capital")
        open_bits = [t for t in res["trades"] if t["open"]]
        check(len(open_bits) <= 1 and (not open_bits or res["trades"][-1]["open"]), f"{sym}: open trade not last")
        print(f"   {sym:<14} strategy {sm['total_return']:>8.1%}  buy&hold {sm['buy_hold_return']:>8.1%}  "
              f"maxDD {sm['max_drawdown']:>7.1%}  streak {sm['longest_losing_streak']}  max rel diff {worst:.1e}")

    port = s1.portfolio_backtest(500000.0)
    parts = [s1._backtest_raw(s, 100000.0) for s in TICKERS]
    summed = [sum(p["equity"][i] for p in parts) for i in range(len(parts[0]["equity"]))]
    check(all(abs(a["value"] - round(b, 2)) < 1e-6 for a, b in zip(port["equity"], summed)), "portfolio != sum of stocks")
    check(close_enough(port["summary"]["final_equity"], summed[-1]), "portfolio final equity wrong")
    check(close_enough(port["summary"]["buy_hold_return"],
                       sum(1 + p["summary"]["buy_hold_return"] for p in parts) / 5 - 1), "portfolio buy-and-hold wrong")
    print(f"   portfolio      strategy {port['summary']['total_return']:>8.1%}  buy&hold {port['summary']['buy_hold_return']:>8.1%}")


# ---------------------------------------------------------------------------
# Hand-built scenarios
# ---------------------------------------------------------------------------
def bars_of(closes):
    return pd.DataFrame({"date": pd.date_range("2020-01-03", periods=len(closes), freq="W-FRI"), "close": closes})


def hand():
    print("3. Hand-built scenarios")
    b = bars_of([100.0, 110.0, 121.0, 100.0, 90.0, 99.0])
    d = b["date"]
    t1 = {"entry_date": d[1], "entry_price": 110.0, "exit_date": d[2], "exit_price": 121.0, "open": False}   # +10%
    t2 = {"entry_date": d[3], "entry_price": 100.0, "exit_date": d[4], "exit_price": 90.0, "open": False}    # -10%
    eq = bt.compound_equity_curve([t1, t2], b, 1000.0)
    # On paper: 1000 flat; entry at 110 -> 1000; exit at 121 -> 1100; flat; entry 100 -> 1100; exit 90 -> 990; flat.
    want = [1000.0, 1000.0, 1100.0, 1100.0, 990.0, 990.0]
    check(all(math.isclose(a, w, rel_tol=1e-12) for a, w in zip(eq, want)), f"hand equity {eq} != {want}")
    s = bt.summarize([t1, t2], b, 1000.0)
    check(math.isclose(s["total_return"], -0.01), f"hand total return {s['total_return']} != -1%")
    check(math.isclose(s["max_drawdown"], -0.10), f"hand drawdown {s['max_drawdown']} != -10% (1100 -> 990)")
    check(math.isclose(s["buy_hold_return"], -0.01), "hand buy-and-hold should be 99/100 - 1 = -1%")
    check(s["longest_losing_streak"] == 1 and s["wins"] == 1 and s["losses"] == 1, "hand streak/wins wrong")
    check(s["win_rate"] == 0.5 and s["open_trade"] is None, "hand win rate / open trade wrong")

    # Open trade at the end: bought at 90 in week 5, marked at 99 -> +10%, reported separately.
    t3 = {"entry_date": d[4], "entry_price": 90.0, "exit_date": d[5], "exit_price": 99.0, "open": True}
    s = bt.summarize([t1, t3], b, 1000.0)
    check(math.isclose(s["final_equity"], 1210.0), f"open trade: final {s['final_equity']} != 1100 x 1.1 = 1210")
    check(math.isclose(s["realised_equity"], 1100.0), "open trade must not count in realised equity")
    check(s["closed_trades"] == 1 and math.isclose(s["open_trade"]["unrealised_return"], 0.10), "open trade stats wrong")

    # Losing streak counts only consecutive losses: L, L, W, L, L, L -> 3
    rets = [-0.1, -0.1, 0.1, -0.1, -0.1, -0.1]
    trades = [{"entry_date": pd.Timestamp(2020, 1, 1) + pd.Timedelta(days=7 * i), "entry_price": 100.0,
               "exit_date": pd.Timestamp(2020, 1, 1), "exit_price": 100 * (1 + r), "open": False} for i, r in enumerate(rets)]
    check(bt.longest_losing_streak(trades) == 3, "streak L,L,W,L,L,L should be 3")
    trades[-1]["open"] = True
    check(bt.longest_losing_streak(trades) == 2, "an open losing trade must not extend the streak")

    # Overlapping trades are refused (one position at a time).
    try:
        bt.compound_equity_curve([t1, {**t2, "entry_date": d[2]}], b, 1000.0)
        check(False, "overlapping trades were accepted")
    except ValueError:
        check(True, "")

    # trades_from_rows: BUY .. SELL pairs at the signal week's close; an unfinished one is open.
    rows = pd.DataFrame({"date": d, "close": b["close"],
                         "state": ["NEUTRAL", "BUY", "SELL", "BUY", "HOLD", "HOLD"]})
    tr = s1.trades_from_rows(rows)
    check(len(tr) == 2 and tr[0]["entry_price"] == 110.0 and tr[0]["exit_price"] == 121.0 and not tr[0]["open"],
          "trades_from_rows: closed trade wrong")
    check(tr[1]["entry_price"] == 100.0 and tr[1]["exit_price"] == 99.0 and tr[1]["open"], "trades_from_rows: open trade wrong")

    # Capital validation
    for bad in (0.0, -5.0, float("nan"), float("inf")):
        check(bt.validate_capital(bad) is not None, f"capital {bad} should be rejected")
    check(bt.validate_capital(100000.0) is None, "1,00,000 should be accepted")
    print("   done")


def main():
    real_data()
    hand()
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
