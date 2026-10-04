# InvestIQ AI

An AI-assisted research app for five NSE-listed Indian stocks (Maruti Suzuki, Reliance, Infosys, HDFC Bank, Bajaj Auto). It is built around three rule-based trading systems taken from real handwritten trading notes, plus a conversational AI layer that explains the numbers but never produces them.

Built as a mini project for the subject **AI**, to show a working, real-world integration of a large language model into a useful product, not a chatbot bolted onto an unrelated app.

It runs **locally on one laptop**: double-click `start.bat` and it opens in the browser. Price data and user data live in a local **MySQL** database.

---

## The core idea

> **Algorithms calculate. AI explains.**

Every price, indicator, signal and backtest result is produced by deterministic, checkable Python code, never by the AI. The AI (Google Gemini) only explains results that were already computed, in plain language. It cannot invent a number, because it never receives raw price data: `app/ai_context.py` gives it a short plain-text summary of values that were calculated beforehand.

Its system prompt holds firm rules: answer only from the given data, never fabricate a figure, never give buy, sell or hold advice in any phrasing, say plainly when something is outside the data (including any stock other than the five), and reply in plain prose. These rules are checked with **real API calls**, not mocks (`scripts/verify_ai.py`).

The page design makes the split visible. Computed values are printed in black ink in the main column. Explanations and AI replies sit in a brass margin column in a different typeface, like a printed ledger annotated by hand.

## What it does

- **Three rule-based trading systems**, transcribed from the author's handwritten notes:
  - **Trend Following**: buys strength on weekly candles when RSI(14) crosses above 60 with the close above its 20-week average, and exits when a weekly close falls below that average (a trailing stop, no target).
  - **Value Buy, a technical pullback entry**: buys weakness. Monthly RSI between 38 and 45 and rising sets the context, a green weekly candle arms a stop-buy, and the trade has a fixed stop and a swing-high target. This is *not* fundamental value investing; the app says so on the page.
  - **Cup & Handle**: long-term monthly pattern detection with three selling ladders (Income, Wealth, Trail). A detected shape is only ever shown as a *possible* cup formation; a human must confirm it before any price levels appear.
- **Honest backtests** with hypothetical money: total return, maximum drawdown, longest losing streak, and a **buy-and-hold benchmark over the same period**, shown side by side. A portfolio page runs Trend Following on all five stocks at once.
- **Margin notes**: a fixed, rule-based explanation beside every reading, so there is always an explanation even without the AI.
- **An AI chat** on every stock page, scoped to that stock.
- **A screener** with filters, a **watchlist**, and a **trade journal** for real trades, with holdings worked out first in, first out (FIFO), the way Indian tax rules treat sales of shares.
- **A position size calculator**: pure arithmetic from capital, risk, entry and stop.

## What the data says (and the app reports plainly)

On data from 2011 to 2 October 2026:

- **Trend Following trailed buy-and-hold on all five stocks.** For example, Maruti Suzuki returned +243.9% against +960.0% for buy-and-hold. Across all five together it returned +100.9% against +689.3%, although with a much smaller worst fall (−18.3%).
- **Value Buy traded rarely and also trailed buy-and-hold.** Bajaj Auto never produced a Value Buy trade, because its monthly RSI only ever *fell* into the 38–45 zone.
- **Cup & Handle finds no possible cup on any of the five stocks** at the notes' strict thresholds. On these strongly rising stocks, a later high never comes back within 8% of an earlier one five or more years before (the closest overshoot was +37%). That is the expected, correct result, and the thresholds were not loosened to "find" cups.

## What it deliberately does not do

It never tells anyone to buy or sell a stock and never predicts prices. A stock-picking recommender was considered and rejected on purpose, because it would contradict the app's own disclaimers and the AI's rules. The app gives the facts and the arithmetic; the decision stays with the person.

## Tech stack

| Layer | Choice |
|---|---|
| Backend | Python, FastAPI, Uvicorn |
| Frontend | Server-rendered Jinja2 templates and vanilla JavaScript (no framework) |
| Charts | TradingView Lightweight Charts 4.2.3, stored in the project (no CDN) |
| Fonts | IBM Plex Serif, Sans and Mono, stored in the project |
| Database | MySQL 8 on the same laptop, through SQLModel and PyMySQL: price history, watchlist, journal and cup confirmations |
| AI | Google Gemini free tier (`gemini-flash-lite-latest`) through the `google-genai` SDK, behind a one-file provider (`app/ai_provider.py`) |
| Data | Daily prices from 2011 for the five stocks, downloaded once from Yahoo Finance; weekly and monthly candles derived from them |
| Hosting | Localhost only, started with `start.bat` |

Total cost: ₹0.

## Running it

Requirements: Windows, Python 3, and (optionally) MySQL 8 and a free Gemini API key.

```
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in what you have:

- `DATABASE_URL`: a MySQL connection, for example `mysql+pymysql://USER:PASSWORD@localhost:3306/DATABASE`. Then load the price data once with `.venv\Scripts\python.exe scripts\setup_db.py`.
- `GEMINI_API_KEY`: free at [aistudio.google.com](https://aistudio.google.com).

Both are optional. Without a database, charts, signals, backtests and the screener run from the CSV files in `data/`, and only the watchlist, journal and cup confirmation say the database isn't configured. Without a key, only the chat says the AI isn't configured.

Then double-click **`start.bat`**. It starts the app on `127.0.0.1:8000` and opens `http://localhost:8000` in the browser.

Prices are a one-time download (the newest completed week is the week ending 2 October 2026). They are never live; the site never contacts Yahoo Finance.

## Verification

Every calculation module has a script in `scripts/` that checks the production code against an independent from-scratch reimplementation, hand-built scenarios with numbers worked out on paper, and rules that must always hold:

| Script | Checks |
|---|---|
| `verify_data.py` | gaps, duplicates, ordering, candle sanity, corporate actions |
| `verify_mysql_load.py` | every value in MySQL equals the CSV files (171,535 values) |
| `verify_indicators.py` | SMA, EMA, Wilder RSI, swing points, RSI zone and trend |
| `verify_trend_following.py` | System 1 states on all five stocks, plus edge cases |
| `verify_backtest.py` | compounding, drawdown, losing streak, buy-and-hold, portfolio |
| `verify_explanations.py` | every label has a note; no advice wording; real figures quoted |
| `verify_value_buy.py` | System 3, including expiry, re-arm, stop exit and no lookahead |
| `verify_cup_pattern.py` | the detector, the handle rule, the three ladders, no lookahead |
| `verify_portfolio_holdings.py` | FIFO holdings against a share-by-share reference |
| `verify_ai.py` | real Gemini calls: grounded numbers, advice refusals, off-list stocks, follow-ups, no markdown (needs the app running) |

Run any of them with `.venv\Scripts\python.exe scripts\<name>.py`. The pages were also checked in a real browser at desktop and phone width.

## Project notes

- `BUILD.md` is the build specification and progress log for this version, including every decision made with the author along the way.
- `docs/v1/` holds the engineering log and notes from the first version, which was hosted online; this version runs locally with MySQL.
