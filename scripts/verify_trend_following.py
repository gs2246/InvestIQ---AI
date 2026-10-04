"""Verify app/systems/trend_following.py (System 1).

1. Cross-check against an INDEPENDENT from-scratch reimplementation of the rules
   (plain Python lists; SMA and RSI come from the already-verified plain-Python
   references in verify_indicators.py). States and DEVELOPING flags must match
   exactly on all five stocks.
2. Invariants on the real signal sequences (grammar of states, each BUY/SELL
   bar really satisfies its rule, SELL markers land on SMA crossings).
3. Hand-built scenarios fed straight into run_state_machine() so every number is
   chosen by hand (level vs crossover, close == SMA, RSI == 60, DEVELOPING
   boundaries, warm-up).
4. The completed-bar rule: an in-progress week is never evaluated.

Traps from v1 handled here: pandas 3 turns None into NaN in string columns (so
states are compared as plain Python lists), and synthetic fixtures with net drift
can push RSI past a threshold before the SMA window opens (so scenarios use
explicit close/SMA/RSI values rather than synthetic prices).

Run:  python scripts/verify_trend_following.py
"""
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from app import prices  # noqa: E402
from app.stocks import TICKERS  # noqa: E402
from app.systems import trend_following as s1  # noqa: E402
from verify_indicators import ref_rsi, ref_sma  # noqa: E402

NAN = float("nan")
failures: list[str] = []
checks = 0


def check(cond: bool, msg: str) -> None:
    global checks
    checks += 1
    if not cond:
        failures.append(msg)


def none_to_str(xs):
    return [x if x is not None else "-" for x in xs]


# ---------------------------------------------------------------------------
# Independent reference implementation of the rules in BUILD.md section 10
# ---------------------------------------------------------------------------
def ref_system1(closes):
    sma = ref_sma(closes, 20)
    rsi = ref_rsi(closes, 14)
    states, dev = [], []
    holding = False
    for i in range(len(closes)):
        if sma[i] is None or rsi[i] is None:
            states.append(None)
            dev.append(False)
            continue
        prev = rsi[i - 1] if i > 0 else None
        above = closes[i] > sma[i]
        if holding:
            dev.append(False)
            if closes[i] >= sma[i]:
                states.append("HOLD")
            else:
                states.append("SELL")
                holding = False
        else:
            cross = prev is not None and prev <= 60 and rsi[i] > 60
            if cross and above:
                states.append("BUY")
                dev.append(False)
                holding = True
            else:
                states.append("NEUTRAL")
                dev.append(bool(above and prev is not None and 50 <= rsi[i] <= 60 and rsi[i] > prev))
    return states, dev


def real_data() -> None:
    print("1+2. Real data: production vs reference, and invariants")
    for symbol in TICKERS:
        df = s1.evaluate(symbol)
        closes = prices.load_completed_prices(symbol, "weekly")["adj_close"].to_list()
        ref_states, ref_dev = ref_system1(closes)
        got_states = [None if s is None else s for s in df["state"].to_list()]
        check(got_states == ref_states, f"{symbol}: states differ from reference")
        check(df["developing"].to_list() == ref_dev, f"{symbol}: developing flags differ from reference")

        # invariants
        prev_state, prev_row = None, None
        buys = sells = 0
        for (_, row) in df.iterrows():
            st = row["state"]
            if st is None:
                check(prev_state is None, f"{symbol}: None state after real state")
                continue
            if st == "BUY":
                buys += 1
                check(prev_state in (None, "NEUTRAL", "SELL"), f"{symbol} {row['date']:%Y-%m-%d}: BUY while in position")
                check(prev_row["rsi"] <= 60 < row["rsi"], f"{symbol} {row['date']:%Y-%m-%d}: BUY without a 60 crossover")
                check(row["close"] > row["sma"], f"{symbol} {row['date']:%Y-%m-%d}: BUY with close not above SMA")
            elif st == "HOLD":
                check(prev_state in ("BUY", "HOLD"), f"{symbol}: HOLD while flat")
                check(row["close"] >= row["sma"], f"{symbol}: HOLD with close below SMA")
            elif st == "SELL":
                sells += 1
                check(prev_state in ("BUY", "HOLD"), f"{symbol}: SELL while flat")
                check(row["close"] < row["sma"], f"{symbol}: SELL with close not below SMA")
                # the marker lands on the bar where the close first falls below the SMA
                check(prev_row["close"] >= prev_row["sma"], f"{symbol} {row['date']:%Y-%m-%d}: SELL not on an SMA crossing")
            elif st == "NEUTRAL":
                check(prev_state in (None, "NEUTRAL", "SELL"), f"{symbol}: NEUTRAL while in position")
                crossed = prev_row is not None and prev_row["rsi"] == prev_row["rsi"] and prev_row["rsi"] <= 60 < row["rsi"]
                check(not (crossed and row["close"] > row["sma"]), f"{symbol}: NEUTRAL on a valid entry bar")
            check(not row["developing"] or st == "NEUTRAL", f"{symbol}: DEVELOPING on a {st} bar")
            prev_state, prev_row = st, row

        check(sells in (buys, buys - 1), f"{symbol}: {buys} BUY vs {sells} SELL")
        cur = s1.current_signal(symbol)
        check(cur is not None and cur["week_ending"] == df["date"].iloc[-1].strftime("%Y-%m-%d"),
              f"{symbol}: current_signal is not the newest completed bar")
        check(cur["in_position"] == (cur["state"] in ("BUY", "HOLD")), f"{symbol}: in_position wrong")
        check((cur["since"] is not None) == cur["in_position"], f"{symbol}: since wrong")
        sig = s1.signals(symbol)
        check(len(sig) == buys + sells and [x["state"] for x in sig] == [x for x in got_states if x in ("BUY", "SELL")],
              f"{symbol}: signals() does not match the BUY/SELL bars")
        print(f"   {symbol:<14} {len(df):>4} weeks  {buys:>2} BUY  {sells:>2} SELL  now: {cur['state']}"
              f"{' + DEVELOPING' if cur['developing'] else ''} (week ending {cur['week_ending']})")


# ---------------------------------------------------------------------------
# Hand-built scenarios
# ---------------------------------------------------------------------------
def scenario(name, rows, want_states, want_dev=None):
    close = [r[0] for r in rows]
    sma = [r[1] for r in rows]
    rsi = [r[2] for r in rows]
    got, dev = s1.run_state_machine(close, sma, rsi)
    check(got == want_states, f"scenario '{name}': states {none_to_str(got)} != {none_to_str(want_states)}")
    if want_dev is not None:
        check(dev == want_dev, f"scenario '{name}': developing {dev} != {want_dev}")


def scenarios() -> None:
    print("3. Hand-built scenarios")
    # A: first bar cannot cross (no previous RSI); then a real 58 -> 62 crossover.
    scenario("A crossover entry",
             [(100, 90, 55), (101, 90, 58), (102, 90, 62)],
             ["NEUTRAL", "NEUTRAL", "BUY"], [False, True, False])

    # B: entry, exit, then RSI stays above 60 (a LEVEL, not a crossover) -> no re-entry
    #    until RSI falls back to <= 60 and crosses again.
    scenario("B level is not a crossover",
             [(100, 90, 50), (101, 90, 62), (89, 90, 63), (95, 90, 64), (96, 90, 58), (97, 90, 61)],
             ["NEUTRAL", "BUY", "SELL", "NEUTRAL", "NEUTRAL", "BUY"],
             [False, False, False, False, False, False])

    # C: a crossover with the close not strictly above the SMA is not an entry.
    scenario("C close below SMA", [(100, 110, 55), (105, 110, 62)], ["NEUTRAL", "NEUTRAL"])
    scenario("C close equal to SMA", [(100, 100, 55), (101, 101, 62)], ["NEUTRAL", "NEUTRAL"])

    # D: HOLD at close == SMA (the deliberate asymmetry), SELL only strictly below.
    scenario("D asymmetry",
             [(100, 90, 55), (101, 90, 62), (95, 95, 60), (94, 95, 59)],
             ["NEUTRAL", "BUY", "HOLD", "SELL"])

    # E: DEVELOPING boundaries (all flat, close > SMA).
    scenario("E developing boundaries",
             [(100, 90, r) for r in (49, 50, 49.9, 55, 54, 59, 60, 60)],
             ["NEUTRAL"] * 8,
             [False, True, False, True, False, True, True, False])
    scenario("E developing needs close above SMA",
             [(100, 100, 55), (100, 100, 56)], ["NEUTRAL", "NEUTRAL"], [False, False])

    # F: warm-up bars have no state; the first evaluable bar has no previous RSI, so it cannot be a BUY.
    scenario("F warm-up",
             [(100, NAN, 55), (100, 90, NAN), (101, 90, 62), (102, 90, 63)],
             [None, None, "NEUTRAL", "NEUTRAL"])

    # G: previous RSI exactly 60 counts as "<= 60".
    scenario("G prev RSI exactly 60", [(100, 90, 60), (101, 90, 60.01)], ["NEUTRAL", "BUY"])

    # H: a position stays open through many HOLDs and RSI plays no part in the exit.
    scenario("H RSI irrelevant to exit",
             [(100, 90, 55), (101, 90, 62), (102, 90, 30), (103, 90, 10), (80, 90, 90)],
             ["NEUTRAL", "BUY", "HOLD", "HOLD", "SELL"])

    # I: immediately after SELL the next bar is evaluated as flat (re-entry possible when RSI re-crosses).
    scenario("I re-entry after SELL",
             [(100, 90, 55), (101, 90, 62), (85, 90, 40), (95, 90, 58), (96, 90, 65)],
             ["NEUTRAL", "BUY", "SELL", "NEUTRAL", "BUY"])
    print("   done")


# ---------------------------------------------------------------------------
# Completed-bar rule
# ---------------------------------------------------------------------------
def completed_bars() -> None:
    print("4. Completed-bar rule")
    real = prices.downloaded_on()
    all_monthly = prices.load_prices("MARUTI.NS", "monthly")
    done_monthly = prices.load_completed_prices("MARUTI.NS", "monthly")
    check(all_monthly["date"].iloc[-1].date() >= real, "expected an in-progress monthly bar in the raw data")
    check(done_monthly["date"].iloc[-1].date() < real, "completed monthly data still contains an in-progress month")
    weekly_last = s1.evaluate("MARUTI.NS")["date"].iloc[-1].date()
    check(weekly_last < real, "System 1 evaluated a week that was not complete")
    print(f"   downloaded_on={real}; last completed week={weekly_last}; "
          f"last completed month={done_monthly['date'].iloc[-1].date()} (raw data has {all_monthly['date'].iloc[-1].date()})")

    # Pretend the download happened ON the last Friday: that week is then in progress.
    original = prices.downloaded_on
    try:
        prices.downloaded_on = lambda: date(2026, 10, 2)
        prices.load_completed_prices.cache_clear()
        check(s1.evaluate("MARUTI.NS")["date"].iloc[-1].date() == date(2026, 9, 25),
              "a download on the Friday must exclude that Friday's week")
        prices.downloaded_on = lambda: date(2026, 10, 3)
        prices.load_completed_prices.cache_clear()
        check(s1.evaluate("MARUTI.NS")["date"].iloc[-1].date() == date(2026, 10, 2),
              "a download the day after the Friday must include that week")
    finally:
        prices.downloaded_on = original
        prices.load_completed_prices.cache_clear()
    print("   done")


def main() -> int:
    real_data()
    scenarios()
    completed_bars()
    print()
    if failures:
        print(f"FAILURES ({len(failures)}):")
        for line in failures[:40]:
            print(f"  {line}")
        return 1
    print(f"All {checks} checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
