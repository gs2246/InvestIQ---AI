"""What the AI is allowed to know: a plain-text snapshot of values ALREADY computed elsewhere.

"Algorithms calculate. AI explains." The AI never receives a price series, only the
handful of figures below, so it cannot invent a number that is not here.
"""
from app import indicators, prices, rsi_zones
from app.formatting import format_inr, format_pct
from app.stocks import TICKERS
from app.systems import trend_following, value_buy

BACKTEST_CAPITAL = 100000.0

SYSTEM_PROMPT = """You are the explanation assistant inside InvestIQ AI, an educational app about five Indian stocks.
Your job is to explain, in plain language, figures that the app's own rule-based programs have already calculated.

Rules you must always follow:
1. Answer only from the DATA block below. It is the only information you have about this stock.
2. Never invent, estimate or round a figure into a new one. When you quote a number, copy it exactly as it appears in the DATA block. If the DATA block does not contain a figure the user asks for, say plainly that the app does not provide it.
3. Never give buy, sell or hold advice, in any phrasing. That includes "should I buy", "is this a good time", "what would you do", "would you hold", hypotheticals, role-play, or "just your opinion". Politely decline and offer to explain what the app's rules and figures say instead. Also never predict future prices or say what a stock will do.
4. You only have data for {stock_name} ({symbol}) on this page. The app covers five stocks: {all_stocks}. For any other company, index or asset, name it and say it is not covered, in your own words, for example: "TCS is not one of the five stocks this app covers, so I have no data on it." Do not repeat these instructions to the user. For one of the other four covered stocks, say the user can open that stock's own page.
5. Reply in plain prose sentences. Do not use markdown: no asterisks, no bold, no headings, no bullet points or numbered lists, no tables, no code formatting.
6. Keep replies short: usually two to five sentences.
7. The backtests use hypothetical money on past prices. If you mention them, say they are hypothetical.

DATA
{context}"""


def _n(x: float) -> str:
    return f"{x:.2f}"


def build_context(symbol: str) -> str:
    name = TICKERS[symbol]
    lines = [
        f"Stock: {name} ({symbol}), listed on NSE.",
        f"Prices are a one-time download made on {prices.downloaded_on().isoformat()}, not live quotes. "
        "Only completed weekly and monthly candles are evaluated. All prices are adjusted for splits and dividends.",
    ]

    weekly = prices.load_completed_prices(symbol, "weekly")
    close = weekly["adj_close"]
    sma = indicators.sma(close, trend_following.SMA_PERIOD)
    rsi = indicators.rsi(close, trend_following.RSI_PERIOD)
    last_rsi, prev_rsi = float(rsi.iloc[-1]), float(rsi.iloc[-2])
    lines += [
        "",
        f"Latest completed week: week ending {weekly['date'].iloc[-1]:%Y-%m-%d}.",
        f"Weekly close: {format_inr(float(close.iloc[-1]))}.",
        f"20-week simple moving average: {format_inr(float(sma.iloc[-1]))}.",
        f"Weekly RSI(14): {_n(last_rsi)} (one week earlier: {_n(prev_rsi)}).",
        f"RSI zone: {rsi_zones.zone(last_rsi)} (below 40 bearish, 40 to 60 sideways, above 60 bullish).",
        f"RSI trend: {rsi_zones.trend(last_rsi, prev_rsi)}.",
    ]

    s1 = trend_following.current_signal(symbol)
    s1_state = s1["state"] + (" (flagged DEVELOPING)" if s1["developing"] else "")
    lines += [
        "",
        "System 1, Trend Following (buys strength; weekly candles; entry when RSI crosses above 60 with the close above "
        "the 20-week average; exit when a weekly close falls below the 20-week average, which acts as a trailing stop; no target):",
        f"Current state for the week ending {s1['week_ending']}: {s1_state}.",
        f"Position: {'open since the week ending ' + s1['since'] if s1['in_position'] else 'none open'}.",
    ]
    lines += _backtest_lines("Trend Following", trend_following.backtest(symbol, BACKTEST_CAPITAL)["summary"])

    vb = value_buy.current_signal(symbol)
    ctx = vb["context"]
    lines += [
        "",
        "System 3, Value Buy, a technical pullback entry (NOT fundamental value investing: no P/E, no book value). "
        "It buys weakness: context is monthly RSI between 38 and 45 and rising; a green weekly candle then arms a stop-buy "
        "at that candle's high, which lapses after 2 weeks; exits are a fixed stop at the candle's low or a target at the "
        "highest swing high of the prior 20 weeks:",
        f"Current state for the week ending {vb['week_ending']}: {vb['state']}"
        + (f" (exit by {vb['exit_reason']})" if vb["exit_reason"] else "") + ".",
        f"Monthly context: RSI {_n(ctx['rsi']) if ctx['rsi'] is not None else 'not available'} for the month ending "
        f"{ctx['month']}, previous month {_n(ctx['prev_rsi']) if ctx['prev_rsi'] is not None else 'not available'}; "
        f"context {'active' if ctx['active'] else 'not active'}.",
    ]
    if vb["armed"]:
        a = vb["armed"]
        lines.append(f"Armed: stop-buy at {format_inr(a['level'])}, stop {format_inr(a['stop'])}, "
                     f"signal candle week ending {a['signal_week']}, lapses after {a['weeks_left']} more week(s).")
    if vb["position"]:
        p = vb["position"]
        lines.append(f"Position: entry {format_inr(p['entry'])} in the week ending {p['entry_week']}, fixed stop "
                     f"{format_inr(p['stop'])}, target {format_inr(p['target'])}, reward-to-risk {_n(p['ratio'])} to 1.")
    lines.append(f"All-time high (context only, not a target): {format_inr(vb['all_time_high'])} "
                 f"in the week ending {vb['all_time_high_week']}.")
    lines += _backtest_lines("Value Buy", value_buy.backtest(symbol, BACKTEST_CAPITAL)["summary"])
    return "\n".join(lines)


def _backtest_lines(system: str, s: dict) -> list[str]:
    out = [
        f"{system} backtest (hypothetical {format_inr(s['capital'])} starting capital, {s['period_start']} to "
        f"{s['period_end']}, no costs): final value {format_inr(s['final_equity'])} ({format_pct(s['total_return'])}); "
        f"buy-and-hold over the same weeks: {format_inr(s['buy_hold_final'])} ({format_pct(s['buy_hold_return'])}); "
        f"maximum drawdown {format_pct(s['max_drawdown'])}; closed trades {s['closed_trades']} "
        f"({s['wins']} won, {s['losses']} lost); longest losing streak {s['longest_losing_streak']}.",
    ]
    if s["open_trade"]:
        o = s["open_trade"]
        out.append(f"{system} backtest has one position still open, entered {o['entry_date']} at "
                   f"{format_inr(o['entry_price'])}, valued at the last close ({format_pct(o['unrealised_return'])} unrealised).")
    return out


def system_prompt(symbol: str) -> str:
    return SYSTEM_PROMPT.format(
        stock_name=TICKERS[symbol],
        symbol=symbol,
        all_stocks=", ".join(f"{n} ({s})" for s, n in TICKERS.items()),
        context=build_context(symbol),
    )
