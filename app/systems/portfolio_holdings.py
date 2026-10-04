"""Holdings from the user's REAL trade journal. Pure computation: no database, no I/O.

Cost basis is FIFO (first in, first out): a SELL uses up the earliest shares bought
first, which is how Indian tax law computes gains on listed equity.

- Entries are processed in trade_date order, not the order they were typed in.
  If a BUY and a SELL share the same date, the BUY is taken first (the order inside a
  day is unknowable, and this avoids a false "sold more than you held"); after that,
  the order they were added (id).
- A SELL larger than the shares held is capped at what is held, and reported in
  `inconsistencies` so the user can fix the journal.
- "Current price" is the latest completed weekly close, a one-time download, not live.

Worked check (BUILD.md): BUY 10 @ 100, BUY 5 @ 120, SELL 8 ->
remaining 2 @ 100 + 5 @ 120, average cost 800 / 7 = 114.29.
"""
from collections import deque

SIDE_ORDER = {"BUY": 0, "SELL": 1}


def _sort_key(e: dict):
    return (str(e["trade_date"]), SIDE_ORDER[e["side"]], e.get("id") or 0)


def compute_holdings(entries: list[dict], current_prices: dict, names: dict) -> dict:
    """entries: dicts with id, symbol, side ('BUY'/'SELL'), quantity (int), price, trade_date.
    current_prices: symbol -> {"price": float, "as_of": "YYYY-MM-DD"} (or missing).
    names: symbol -> display name.
    """
    lots: dict[str, deque] = {}
    realised: dict[str, float] = {}
    bought: dict[str, int] = {}
    inconsistencies: list[dict] = []

    for e in sorted(entries, key=_sort_key):
        sym, qty, price = e["symbol"], int(e["quantity"]), float(e["price"])
        book = lots.setdefault(sym, deque())
        realised.setdefault(sym, 0.0)
        bought.setdefault(sym, 0)
        if e["side"] == "BUY":
            book.append({"quantity": qty, "price": price, "trade_date": str(e["trade_date"])})
            bought[sym] += qty
            continue
        held = sum(lot["quantity"] for lot in book)
        to_sell = qty
        if qty > held:
            name = names.get(sym, sym)
            if held == 0:
                message = (f"The SELL of {qty} {name} shares on {e['trade_date']} has no shares bought before it, "
                           f"so it is ignored. Check whether a BUY is missing or a date is wrong.")
            else:
                message = (f"The SELL of {qty} {name} shares on {e['trade_date']} is more than the {held} held then, "
                           f"so only {held} were counted. Check whether a BUY is missing or a date is wrong.")
            inconsistencies.append({
                "entry_id": e.get("id"), "symbol": sym, "trade_date": str(e["trade_date"]),
                "requested": qty, "held": held, "message": message,
            })
            to_sell = held
        while to_sell > 0:
            lot = book[0]
            used = min(lot["quantity"], to_sell)
            realised[sym] += used * (price - lot["price"])
            lot["quantity"] -= used
            to_sell -= used
            if lot["quantity"] == 0:
                book.popleft()

    holdings = []
    for sym in sorted(lots, key=lambda s: names.get(s, s)):
        book = list(lots[sym])
        quantity = sum(lot["quantity"] for lot in book)
        cost = sum(lot["quantity"] * lot["price"] for lot in book)
        cp = current_prices.get(sym)
        price = cp["price"] if cp else None
        market = quantity * price if price is not None else None
        unrealised = market - cost if market is not None else None
        holdings.append({
            "symbol": sym,
            "name": names.get(sym, sym),
            "quantity": quantity,
            "avg_cost": round(cost / quantity, 2) if quantity else None,
            "cost_basis": round(cost, 2),
            "current_price": price,
            "price_as_of": cp["as_of"] if cp else None,
            "market_value": round(market, 2) if market is not None else None,
            "unrealised_pnl": round(unrealised, 2) if unrealised is not None and quantity else (0.0 if quantity == 0 else None),
            "unrealised_pct": round(unrealised / cost, 6) if unrealised is not None and cost else None,
            "realised_pnl": round(realised[sym], 2),
            "shares_bought": bought[sym],
            "lots": [{**lot} for lot in book],
        })

    open_rows = [h for h in holdings if h["quantity"] > 0]
    totals = {
        "cost_basis": round(sum(h["cost_basis"] for h in open_rows), 2),
        "market_value": round(sum(h["market_value"] for h in open_rows if h["market_value"] is not None), 2),
        "unrealised_pnl": round(sum(h["unrealised_pnl"] for h in open_rows if h["unrealised_pnl"] is not None), 2),
        "realised_pnl": round(sum(h["realised_pnl"] for h in holdings), 2),
    }
    return {"holdings": holdings, "totals": totals, "inconsistencies": inconsistencies}
