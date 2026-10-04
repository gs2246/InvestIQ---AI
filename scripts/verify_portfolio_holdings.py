"""Verify app/systems/portfolio_holdings.py (FIFO holdings from the real trade journal).

1. The BUILD.md worked check: BUY 10 @ 100, BUY 5 @ 120, SELL 8 -> 2 @ 100 + 5 @ 120,
   average cost 800 / 7 = 114.29.
2. An independent reimplementation that tracks every single share (a queue of
   one-share units, a different method from the lot-based production code), compared
   on 2,000 random journals: quantity, cost basis, average cost, realised P&L,
   unrealised P&L and inconsistencies must all match.
3. Hand-built edge cases: order by trade_date not insertion, same-date BUY before
   SELL, oversized SELL capped and reported, fully sold stock keeps its realised P&L,
   missing current price, totals.

Run:  python scripts/verify_portfolio_holdings.py
"""
import math
import random
import sys
from collections import deque
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.systems.portfolio_holdings import compute_holdings  # noqa: E402

failures: list[str] = []
checks = 0
NAMES = {"AAA": "Alpha", "BBB": "Beta", "CCC": "Gamma"}


def check(cond, msg):
    global checks
    checks += 1
    if not cond:
        failures.append(msg)


def entry(i, sym, side, qty, price, d):
    return {"id": i, "symbol": sym, "side": side, "quantity": qty, "price": price, "trade_date": d}


# ---------------------------------------------------------------------------
def ref(entries, prices):
    """Share-by-share FIFO. Each share bought is one queue item holding its cost."""
    order = sorted(entries, key=lambda e: (str(e["trade_date"]), 0 if e["side"] == "BUY" else 1, e["id"]))
    shares, realised, bad = {}, {}, 0
    for e in order:
        q = shares.setdefault(e["symbol"], deque())
        realised.setdefault(e["symbol"], 0.0)
        if e["side"] == "BUY":
            q.extend([float(e["price"])] * e["quantity"])
        else:
            if e["quantity"] > len(q):
                bad += 1
            for _ in range(min(e["quantity"], len(q))):
                realised[e["symbol"]] += float(e["price"]) - q.popleft()
    out = {}
    for sym, q in shares.items():
        cost = sum(q)
        out[sym] = {"quantity": len(q), "cost": cost, "realised": realised[sym],
                    "unrealised": (len(q) * prices[sym] - cost) if sym in prices else None}
    return out, bad


def worked_check():
    print("1. Worked check from BUILD.md")
    es = [entry(1, "AAA", "BUY", 10, 100, "2024-01-01"), entry(2, "AAA", "BUY", 5, 120, "2024-02-01"),
          entry(3, "AAA", "SELL", 8, 130, "2024-03-01")]
    r = compute_holdings(es, {"AAA": {"price": 150.0, "as_of": "2026-10-02"}}, NAMES)
    h = r["holdings"][0]
    check(h["quantity"] == 7, f"remaining quantity {h['quantity']} != 7")
    check([(l["quantity"], l["price"]) for l in h["lots"]] == [(2, 100.0), (5, 120.0)], f"lots {h['lots']}")
    check(h["cost_basis"] == 800.0 and h["avg_cost"] == 114.29, f"cost {h['cost_basis']} / avg {h['avg_cost']}")
    check(h["realised_pnl"] == 8 * (130 - 100), f"realised {h['realised_pnl']} != 240 (8 shares bought at 100, sold at 130)")
    check(h["unrealised_pnl"] == 7 * 150 - 800, f"unrealised {h['unrealised_pnl']} != 250")
    check(not r["inconsistencies"], "worked check should have no inconsistencies")
    print(f"   remaining {h['quantity']}: lots {[(l['quantity'], l['price']) for l in h['lots']]}, "
          f"average cost {h['avg_cost']}, realised {h['realised_pnl']}, unrealised {h['unrealised_pnl']}")


def random_journals(n=2000):
    print("2. Independent share-by-share reimplementation on random journals")
    rng = random.Random(20261003)
    mismatches = 0
    for case in range(n):
        es, start = [], date(2020, 1, 1)
        for i in range(1, rng.randint(1, 25) + 1):
            sym = rng.choice(list(NAMES))
            side = rng.choice(["BUY", "BUY", "SELL"])
            es.append(entry(i, sym, side, rng.randint(1, 40), round(rng.uniform(10, 500), 2),
                            (start + timedelta(days=rng.randint(0, 900))).isoformat()))
        rng.shuffle(es)  # insertion order must not matter (ids stay as tiebreak)
        prices = {s: round(rng.uniform(10, 500), 2) for s in NAMES if rng.random() < 0.85}
        cur = {s: {"price": p, "as_of": "2026-10-02"} for s, p in prices.items()}
        got = compute_holdings(es, cur, NAMES)
        want, bad = ref(es, prices)
        ok = len(got["inconsistencies"]) == bad and {h["symbol"] for h in got["holdings"]} == set(want)
        for h in got["holdings"]:
            w = want[h["symbol"]]
            ok &= h["quantity"] == w["quantity"]
            ok &= math.isclose(h["cost_basis"], round(w["cost"], 2), abs_tol=0.011)
            ok &= math.isclose(h["realised_pnl"], round(w["realised"], 2), abs_tol=0.011)
            if w["quantity"]:
                ok &= math.isclose(h["avg_cost"], round(w["cost"] / w["quantity"], 2), abs_tol=0.011)
                if w["unrealised"] is None:
                    ok &= h["unrealised_pnl"] is None
                else:
                    ok &= math.isclose(h["unrealised_pnl"], round(w["unrealised"], 2), abs_tol=0.011)
            else:
                ok &= h["avg_cost"] is None and not h["lots"]
        if not ok:
            mismatches += 1
            if mismatches <= 3:
                failures.append(f"random journal {case} differs from the reference")
    check(mismatches == 0, f"{mismatches} of {n} random journals differ")
    print(f"   {n} journals compared, {mismatches} mismatches")


def edge_cases():
    print("3. Edge cases")
    # Order by trade_date, not insertion: the SELL was typed first but happened later.
    es = [entry(1, "AAA", "SELL", 5, 200, "2024-06-01"), entry(2, "AAA", "BUY", 10, 100, "2024-01-01")]
    r = compute_holdings(es, {}, NAMES)
    check(not r["inconsistencies"] and r["holdings"][0]["quantity"] == 5, "entries must be ordered by trade_date")
    # Same date: BUY before SELL even if the SELL was added first.
    es = [entry(1, "AAA", "SELL", 3, 110, "2024-01-01"), entry(2, "AAA", "BUY", 3, 100, "2024-01-01")]
    r = compute_holdings(es, {}, NAMES)
    check(not r["inconsistencies"] and r["holdings"][0]["realised_pnl"] == 30.0, "same-date BUY should come first")
    # Oversized SELL: capped, reported, nothing negative.
    es = [entry(1, "AAA", "BUY", 4, 100, "2024-01-01"), entry(2, "AAA", "SELL", 10, 90, "2024-02-01")]
    r = compute_holdings(es, {"AAA": {"price": 95.0, "as_of": "x"}}, NAMES)
    h = r["holdings"][0]
    check(h["quantity"] == 0 and h["realised_pnl"] == -40.0, f"capped sell: qty {h['quantity']} realised {h['realised_pnl']}")
    check(len(r["inconsistencies"]) == 1 and r["inconsistencies"][0]["requested"] == 10 and r["inconsistencies"][0]["held"] == 4,
          f"inconsistency report {r['inconsistencies']}")
    # Fully sold stock keeps its realised P&L, has no average cost and no unrealised P&L.
    check(h["avg_cost"] is None and h["unrealised_pnl"] == 0.0 and h["lots"] == [], "fully sold row wrong")
    check(h["shares_bought"] == 4 and "only 4 were counted" in r["inconsistencies"][0]["message"], "capped-sell wording")
    # A SELL with nothing bought before it: ignored, said plainly, and not a "sold" stock.
    r = compute_holdings([entry(1, "BBB", "SELL", 3, 50, "2024-01-01")], {}, NAMES)
    check(r["holdings"][0]["shares_bought"] == 0 and "no shares bought before it" in r["inconsistencies"][0]["message"]
          and "Beta" in r["inconsistencies"][0]["message"], f"stray SELL wording: {r['inconsistencies']}")
    # Missing current price: unrealised unknown, not zero.
    es = [entry(1, "BBB", "BUY", 2, 50, "2024-01-01")]
    h = compute_holdings(es, {}, NAMES)["holdings"][0]
    check(h["current_price"] is None and h["unrealised_pnl"] is None and h["market_value"] is None, "missing price handling")
    # Totals add up across stocks; closed rows only add realised P&L.
    es = [entry(1, "AAA", "BUY", 10, 100, "2024-01-01"), entry(2, "BBB", "BUY", 5, 200, "2024-01-01"),
          entry(3, "CCC", "BUY", 1, 10, "2024-01-01"), entry(4, "CCC", "SELL", 1, 15, "2024-02-01")]
    cur = {"AAA": {"price": 110.0, "as_of": "x"}, "BBB": {"price": 190.0, "as_of": "x"}, "CCC": {"price": 1.0, "as_of": "x"}}
    t = compute_holdings(es, cur, NAMES)["totals"]
    check(t == {"cost_basis": 2000.0, "market_value": 2050.0, "unrealised_pnl": 50.0, "realised_pnl": 5.0}, f"totals {t}")
    # Decimal-like prices (as MySQL returns) are accepted.
    from decimal import Decimal
    h = compute_holdings([entry(1, "AAA", "BUY", 3, Decimal("123.45"), date(2024, 1, 1))], {}, NAMES)["holdings"][0]
    check(h["cost_basis"] == 370.35, "Decimal prices and date objects should work")
    print("   done")


def main():
    worked_check()
    random_journals()
    edge_cases()
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
