"""Verify app/explanations.py (the margin notes).

1. Exhaustive: every label a system can produce has exactly one template, and no
   template exists for a label that cannot occur.
2. Every note renders across a dense grid of inputs: no leftover {placeholders},
   at most two sentences, no markdown, no advice or prediction wording.
3. Notes quote the computed numbers, and pick the right template, on real data.
4. Prints today's real notes so the wording can be read through with the user.

Run:  python scripts/verify_explanations.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import explanations as ex  # noqa: E402
from app import indicators, prices, rsi_zones  # noqa: E402
from app.formatting import format_inr, format_pct  # noqa: E402
from app.stocks import TICKERS  # noqa: E402
from app.systems import trend_following as s1  # noqa: E402
from app.systems import value_buy as vb  # noqa: E402
from app.systems import cup_pattern  # noqa: E402

failures: list[str] = []
checks = 0
BANNED = ["you should", "we recommend", "recommend", "should buy", "should sell", "buy now", "sell now",
          "will rise", "will fall", "will go", "guarantee", "expect the price", "time to buy", "time to sell"]


def check(cond, msg):
    global checks
    checks += 1
    if not cond:
        failures.append(msg)


def sentences(text: str) -> int:
    # a full stop followed by a space or the end; decimals like 29.91 do not count
    return len(re.findall(r"[.!?](?=\s|$)", text))


def quality(text: str, where: str) -> None:
    check(bool(text and text.strip()), f"{where}: empty note")
    check("{" not in text and "}" not in text, f"{where}: unfilled placeholder: {text}")
    check(1 <= sentences(text) <= 2, f"{where}: {sentences(text)} sentences: {text}")
    check(not re.search(r"[*#`]|\]\(|^\s*[-+] ", text), f"{where}: markdown in note: {text}")
    low = text.lower()
    hit = [b for b in BANNED if b in low]
    check(not hit, f"{where}: advice/prediction wording {hit}: {text}")
    check("n/a" not in text and "nan" not in low.split(), f"{where}: missing value shown: {text}")
    check(len(text) <= 420, f"{where}: note too long ({len(text)} chars)")


def exhaustive() -> None:
    print("1. Every label has exactly one template")
    check(set(ex.ZONE_NOTES) == set(rsi_zones.ZONES), f"zone templates {set(ex.ZONE_NOTES)} vs labels {set(rsi_zones.ZONES)}")
    check(set(ex.TREND_NOTES) == set(rsi_zones.TRENDS), f"trend templates {set(ex.TREND_NOTES)} vs labels {set(rsi_zones.TRENDS)}")
    check(set(ex.SYSTEM1_NOTES) == set(s1.STATES) | {"DEVELOPING"}, f"System 1 templates {set(ex.SYSTEM1_NOTES)}")
    outcomes = set()
    for ret, bh, closed, open_ in ((0.5, 2.0, 5, None), (2.0, 0.5, 5, None), (1.0, 1.005, 5, None), (0.0, 1.0, 0, None)):
        outcomes.add(ex.backtest_outcome({"total_return": ret, "buy_hold_return": bh, "closed_trades": closed, "open_trade": open_}))
    check(outcomes == set(ex.BACKTEST_NOTES), f"reachable backtest outcomes {outcomes} vs templates {set(ex.BACKTEST_NOTES)}")
    check(set(ex.CUP_NOTES) == {"NONE", "POSSIBLE", "CONFIRMED"}, f"Cup templates {set(ex.CUP_NOTES)}")
    vb_keys = {s for s in vb.STATES if s != "SELL"} | {f"SELL:{r}" for r in vb.EXIT_REASONS}
    check(set(ex.VALUE_BUY_NOTES) == vb_keys, f"Value Buy templates {set(ex.VALUE_BUY_NOTES)} vs {vb_keys}")
    print(f"   zones {len(ex.ZONE_NOTES)}, trends {len(ex.TREND_NOTES)}, System 1 {len(ex.SYSTEM1_NOTES)}, "
          f"Value Buy {len(ex.VALUE_BUY_NOTES)}, backtest {len(ex.BACKTEST_NOTES)}")


def grid() -> None:
    print("2. Every note renders cleanly across a dense grid")
    seen_z, seen_t, seen_s = set(), set(), set()
    for i in range(0, 401):
        rsi = i * 0.25
        z = rsi_zones.zone(rsi)
        seen_z.add(z)
        quality(ex.rsi_zone_note(z, rsi), f"zone {z} at {rsi}")
        for delta in (-3.0, -0.5, 0.0, 0.5, 3.0):
            prev = rsi - delta
            t = rsi_zones.trend(rsi, prev)
            seen_t.add(t)
            note = ex.rsi_trend_note(t, rsi, prev)
            quality(note, f"trend {t} at {rsi}/{prev}")
            check(("extended" in note) == (rsi > 80 or rsi < 20), f"extended wording wrong at RSI {rsi}: {note}")
    check(seen_z == set(rsi_zones.ZONES) and seen_t == set(rsi_zones.TRENDS), "grid did not reach every label")

    base = {"week_ending": "2026-10-02", "close": 11386.0, "sma": 13167.19, "rsi": 29.91, "since": "2026-05-01"}
    cases = [("BUY", False, 105.0, 100.0, 61.2), ("HOLD", False, 100.0, 100.0, 45.0), ("SELL", False, 95.0, 100.0, 40.0),
             ("NEUTRAL", False, 95.0, 100.0, 40.0), ("NEUTRAL", False, 105.0, 100.0, 70.0), ("NEUTRAL", True, 105.0, 100.0, 55.0)]
    for state, dev, close, sma, rsi in cases:
        cur = {**base, "state": state, "developing": dev, "close": close, "sma": sma, "rsi": rsi}
        note = ex.system1_note(cur)
        seen_s.add("DEVELOPING" if dev else state)
        quality(note, f"System 1 {state}{' DEVELOPING' if dev else ''}")
        check(format_inr(close) in note or state == "DEVELOPING" or dev, f"System 1 {state}: close not quoted: {note}")
    check(seen_s == set(ex.SYSTEM1_NOTES), f"System 1 cases cover {seen_s}")

    ctx_on = {"month": "2026-09-30", "rsi": 41.2, "prev_rsi": 39.8, "active": True}
    ctx_off = {"month": "2026-09-30", "rsi": 47.0, "prev_rsi": 49.0, "active": False}
    armed = {"signal_week": "2026-09-25", "level": 1185.8, "stop": 1138.1, "weeks_left": 2}
    pos = {"signal_week": "2026-08-07", "entry_week": "2026-08-14", "entry": 1185.8, "stop": 1138.1,
           "target": 1347.73, "ratio": 3.39, "last_close": 1200.0}
    vb_cases = [
        ("NEUTRAL", {"state": "NEUTRAL", "exit_reason": None, "context": ctx_on, "armed": None, "position": None}),
        ("NEUTRAL", {"state": "NEUTRAL", "exit_reason": None, "context": ctx_off, "armed": None, "position": None}),
        ("ARMED", {"state": "ARMED", "exit_reason": None, "context": ctx_on, "armed": armed, "position": None}),
        ("ARMED", {"state": "ARMED", "exit_reason": None, "context": ctx_on, "armed": {**armed, "weeks_left": 1}, "position": None}),
        ("BUY", {"state": "BUY", "exit_reason": None, "context": ctx_on, "armed": None, "position": pos}),
        ("HOLD", {"state": "HOLD", "exit_reason": None, "context": ctx_off, "armed": None, "position": pos}),
        ("SELL:stop", {"state": "SELL", "exit_reason": "stop", "context": ctx_off, "armed": None,
                       "position": {**pos, "exit_price": 1138.1}}),
        ("SELL:target", {"state": "SELL", "exit_reason": "target", "context": ctx_off, "armed": None,
                         "position": {**pos, "exit_price": 1347.73}}),
    ]
    seen_vb = set()
    for key, cur in vb_cases:
        note = ex.value_buy_note(cur)
        seen_vb.add(ex.value_buy_key(cur))
        quality(note, f"Value Buy {key}")
    check(seen_vb == set(ex.VALUE_BUY_NOTES), f"Value Buy cases cover {seen_vb}")
    check("1 more week." in ex.value_buy_note(vb_cases[3][1]), "singular 'week' wording")
    check("is not active" in ex.value_buy_note(vb_cases[1][1]) and "is active" in ex.value_buy_note(vb_cases[0][1]),
          "NEUTRAL context wording")

    cup_status = {"status": "POSSIBLE", "as_of": "2026-09-30",
                  "cup": {"left_rim_date": "2015-01-31", "right_rim_date": "2021-03-31", "months": 74, "depth": 0.355,
                          "handle_start": "2021-04-30", "handle_end": "2021-06-30"},
                  "levels": {"buy_point": 99.5, "entry": 103.48, "stop": 75.62, "entry_triggered": True,
                             "entry_date": "2021-08-31"}}
    seen_cup = set()
    for st, conf in (({"status": "NONE", "as_of": "2026-09-30"}, False), (cup_status, False), (cup_status, True),
                     ({**cup_status, "levels": {**cup_status["levels"], "entry_triggered": False, "entry_date": None}}, True)):
        note = ex.cup_note(st, conf)
        seen_cup.add(ex.cup_key(st, conf))
        quality(note, f"Cup {ex.cup_key(st, conf)}")
        if st["status"] == "POSSIBLE" and not conf:
            check("₹" not in note, "an unconfirmed cup note must not reveal any price level")
    check(seen_cup == set(ex.CUP_NOTES), f"Cup cases cover {seen_cup}")

    summary = {"capital": 100000.0, "period_start": "2011-05-20", "period_end": "2026-10-02", "final_equity": 343900.0,
               "total_return": 2.439, "buy_hold_return": 9.6, "buy_hold_final": 1060000.0, "max_drawdown": -0.4,
               "closed_trades": 22, "open_trade": None}
    variants = {
        "trailed": summary,
        "beat": {**summary, "total_return": 12.0, "final_equity": 1300000.0},
        "matched": {**summary, "total_return": 9.601, "final_equity": 1060100.0},
        "no_trades": {**summary, "closed_trades": 0, "total_return": 0.0, "final_equity": 100000.0, "max_drawdown": 0.0},
        "open": {**summary, "open_trade": {"entry_date": "2026-05-01"}},
    }
    for name, sm in variants.items():
        note = ex.backtest_note(sm)
        quality(note, f"backtest {name}")
        quality(ex.backtest_note(sm, portfolio=True), f"portfolio backtest {name}")
        check(format_inr(sm["capital"]) in note, f"backtest {name}: capital not quoted")
        check(("still open" in note) == (sm["open_trade"] is not None), f"backtest {name}: open-position wording wrong")
    print("   done")


def real_data() -> None:
    print("3+4. Real data, with every note printed for reading")
    for sym in TICKERS:
        df = prices.load_completed_prices(sym, "weekly")
        rsi = indicators.rsi(df["adj_close"], 14)
        last, prev = float(rsi.iloc[-1]), float(rsi.iloc[-2])
        z, t = rsi_zones.zone(last), rsi_zones.trend(last, prev)
        zn, tn = ex.rsi_zone_note(z, last), ex.rsi_trend_note(t, last, prev)
        cur = s1.current_signal(sym)
        sn = ex.system1_note(cur)
        bt = s1.backtest(sym, 100000.0)["summary"]
        bn = ex.backtest_note(bt)
        for label, note in (("zone", zn), ("trend", tn), ("signal", sn), ("backtest", bn)):
            quality(note, f"{sym} {label}")
        check(f"{last:.2f}" in zn, f"{sym}: zone note does not quote RSI {last:.2f}")
        check(format_inr(cur["close"]) in sn or cur["developing"], f"{sym}: signal note does not quote the close")
        check(format_pct(bt["total_return"]) in bn and format_pct(bt["buy_hold_return"]) in bn, f"{sym}: backtest note figures")
        check(ex.backtest_outcome(bt) == ("beat" if bt["total_return"] > bt["buy_hold_return"] + 0.01 else
                                          "trailed" if bt["total_return"] < bt["buy_hold_return"] - 0.01 else "matched"),
              f"{sym}: wrong backtest template")
        vcur = vb.current_signal(sym)
        vn = ex.value_buy_note(vcur)
        vbn = ex.backtest_note(vb.backtest(sym, 100000.0)["summary"])
        quality(vn, f"{sym} Value Buy")
        cn = ex.cup_note(cup_pattern.current_status(sym), False)
        quality(cn, f"{sym} Cup & Handle")
        quality(vbn, f"{sym} Value Buy backtest")
        if vcur["context"]["rsi"] is not None:
            check(f"{vcur['context']['rsi']:.2f}" in vn or vcur["state"] != "NEUTRAL", f"{sym}: Value Buy note misses monthly RSI")
        print(f"\n   {TICKERS[sym]} ({z} / {t} / {cur['state']}{' + DEVELOPING' if cur['developing'] else ''} / Value Buy {vcur['state']})")
        for label, note in (("RSI zone", zn), ("RSI trend", tn), ("Signal", sn), ("Backtest", bn),
                            ("Value Buy", vn), ("Value Buy backtest", vbn)):
            print(f"     [{label}] {note}")
    port = s1.portfolio_backtest(100000.0)["summary"]
    pn = ex.backtest_note(port, portfolio=True)
    quality(pn, "portfolio")
    print(f"\n   Portfolio\n     [Backtest] {pn}")


def main() -> int:
    exhaustive()
    grid()
    real_data()
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
