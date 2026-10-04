# BUILD.md — InvestIQ AI v2 build specification

**Audience: Claude Code.** This file is your complete instruction set for building InvestIQ AI v2 from an empty folder. Read it fully before doing anything. It is the single source of truth for this rebuild; where anything else disagrees with it, this file wins.

Background material lives in `docs/v1/`:
- `docs/v1/ENGINEERING_LOG.md` — the full v1 engineering log (originally named `CLAUDE.md`). It records why every decision was made and every bug that was found. Consult it whenever this file is silent on a detail. Ignore its Render-, Neon- and cold-start-specific instructions; those are superseded below.
- `docs/v1/README.md` — v1's public README.
- `docs/v1/PRESENTING.md` — the user's demo-day notes.

---

## 1. What this rebuild is

InvestIQ AI v1 was a complete, working app. **v2 rebuilds the same product with the same architecture. Exactly two things change:**

| | v1 | v2 |
|---|---|---|
| Hosting | Render free tier | **Localhost only** — the app runs on his own laptop, started by double-clicking `start.bat` |
| Database | Neon serverless Postgres (watchlist/journal only); prices as CSV files | **MySQL** — holds the stock price data *and* the watchlist, journal and cup confirmations |

**Everything else is unchanged and must be rebuilt as it was:** FastAPI + Jinja2 + vanilla JS, SQLModel, TradingView Lightweight Charts, Google Gemini through a swappable provider, the Ledger design, all three trading systems with their exact rules, the backtests, the AI guardrails, the screener, watchlist, journal, holdings, portfolio page, position size calculator, and every polish and UX item listed in section 13. Do not add features, remove features, swap libraries, or "improve" trading rules.

## 2. Core philosophy

**"Algorithms calculate. AI explains."** Every price, indicator, signal and backtest number is produced by deterministic, auditable Python. The AI only explains values that were already computed. It never receives raw price data, so it cannot invent a number. The UI makes "computed by algorithm" versus "interpreted by AI" visually obvious at a glance: computed values in ink in the main column, AI and explanation text in brass in a margin column, like a printed ledger annotated by hand.

The app never tells anyone to buy, sell or hold, and never predicts prices. A stock-picking recommender was considered and deliberately rejected because it would contradict the app's own disclaimers. If anyone asks for one, raise it as a product decision about the disclaimers first; do not build toward it.

## 3. How to work with this user

The user is **Gaurang**, a second-year B.Tech ECE student. He is a **beginner at engineering** and the **expert on the trading content** (the three systems come from his own handwritten notes).

- **Explain before acting.** Before any terminal command, say in plain words what it does and why. Never assume he knows a command, flag, tool or concept.
- **One phase at a time.** Build a phase completely, verify it (section 15), then stop and report: what was built, how it was verified, anything surprising, and a suggested Git commit message. Wait for him to say "continue" before starting the next phase.
- **Never move forward on a broken state.**
- **Decisions are options with trade-offs.** If something genuinely needs a choice, describe each option, what it does and which you'd recommend. Don't ask him to name technologies he may not know.
- **Never re-derive, reinterpret or "improve" the trading rules in sections 9–12.** If you find a real ambiguity, stop and ask.
- **Things only he can do** (installing MySQL through its installer, choosing passwords, getting a Gemini API key, creating a GitHub repo): walk him through them step by step, then wait.
- **Keep the progress tracker** at the bottom of this file current. Show it at the start of every session.

## 4. Hard constraints — non-negotiable

- **No Docker, ever.** Nothing he has to install or run locally. Native Windows 11, no WSL.
- **Single-command startup.** Double-clicking `start.bat` starts the whole app.
- **Secrets only in `.env`** (gitignored). `.env.example` is committed with placeholder values only. If he pastes a real key into chat, remind him it may persist in chat logs and that he can regenerate it.
- **Works without AI.** With no `GEMINI_API_KEY`, every page and endpoint still works; only the chat shows a clear "AI is not configured" message.
- **Works without a database.** With no `DATABASE_URL` (or MySQL unreachable), charts, signals, backtests and the screener still work from the committed CSV files; only watchlist, journal, holdings and cup confirmation show a clear "database isn't configured" message (HTTP 503 from their API routes).
- **The site never depends on Yahoo Finance being up.** Yahoo is queried only by the one-time download script.
- **₹0 budget.** Free tiers only.
- **Localhost only — final decision.** No cloud hosting (no Render, Vercel, ngrok or similar) and no cloud database. Do not suggest deployment options; the user has locked this in. Demos run from his own laptop.

## 5. Locked tech stack

| Layer | Choice |
|---|---|
| Language | Python in a `.venv` virtual environment (Windows) |
| Web framework | FastAPI + Uvicorn |
| Templates | Jinja2, server-rendered HTML |
| Frontend | Vanilla JavaScript, no framework, every `<script>` tag uses `defer` |
| Charts | TradingView Lightweight Charts **v4.2.3**, vendored at `app/static/vendor/lightweight-charts.js` (no CDN) |
| Fonts | IBM Plex Serif / Sans / Mono, 400 and 600, self-hosted woff2 in `app/static/fonts/` (no Google Fonts) |
| Database | **MySQL 8.4 LTS Community Server**, local install via the official Windows MSI + MySQL Configurator |
| ORM | **SQLModel**, driver **PyMySQL** (`mysql+pymysql://…`) |
| Data | `yfinance` + `pandas` |
| AI | Google Gemini free tier, model alias **`gemini-flash-lite-latest`**, through `app/ai_provider.py`. Use Google's current official Python SDK (check which package is current before installing). |
| Hosting | Localhost only, via `start.bat` |

Pin every dependency to its actually-installed version in `requirements.txt`. Verification-only tools (Playwright, matplotlib) are installed temporarily and uninstalled afterwards; they never go in `requirements.txt`.

## 6. Repository layout

```
investiq/
├── BUILD.md                    # this file
├── CLAUDE.md                   # imports BUILD.md so Claude Code loads it every session
├── README.md                   # rewritten in Phase 13 (v1 README updated for localhost + MySQL)
├── PRESENTING.md               # v1's demo notes, updated in Phase 13
├── docs/v1/                    # v1 reference material (read-only)
├── start.bat
├── requirements.txt
├── .env.example
├── .gitignore                  # .venv/, .env, __pycache__/, *.pyc
├── data/                       # committed CSVs: the seed for MySQL and the fallback when no DB
│   ├── raw/  daily/  weekly/  monthly/
├── app/
│   ├── main.py                 # app, routes, exception handler, static mount, lifespan
│   ├── stocks.py               # TICKERS dict — single source of truth for the 5 stocks
│   ├── db.py                   # engine, is_configured(), init_db(), session helper
│   ├── models.py               # all SQLModel tables
│   ├── prices.py               # cached price loader: MySQL first, CSV fallback
│   ├── indicators.py           # sma, ema, rsi (Wilder), swing_points
│   ├── rsi_zones.py            # zone() and trend()
│   ├── explanations.py         # deterministic margin-note text
│   ├── ai_provider.py          # swappable Gemini provider
│   ├── ai_context.py           # builds the AI's context from computed values only
│   ├── systems/
│   │   ├── trend_following.py  # System 1
│   │   ├── cup_pattern.py      # System 2
│   │   ├── value_buy.py        # System 3
│   │   ├── backtest.py         # shared compounding + summary helpers
│   │   └── portfolio_holdings.py
│   ├── templates/              # _macros.html, home, stock, portfolio, screener, watchlist, journal, error
│   └── static/                 # style.css, fonts/, vendor/, og-image.png, js/
└── scripts/
    ├── download_data.py  resample_data.py  verify_data.py
    ├── setup_db.py              # creates tables, loads CSVs into MySQL (idempotent)
    ├── verify_mysql_load.py     # MySQL contents == CSV contents
    └── verify_*.py              # one per calculation module
```

`CLAUDE.md` contains only an import line for this file plus a pointer to `docs/v1/`. Do not put a copy of v1's `CLAUDE.md` in the project root — its Render instructions would conflict.

## 7. Configuration

`.env.example`:
```
# Local MySQL (Phase 2). Format: mysql+pymysql://USER:PASSWORD@HOST:PORT/DATABASE
DATABASE_URL=mysql+pymysql://investiq_user:CHANGE_ME@localhost:3306/investiq
# Free key from https://aistudio.google.com
GEMINI_API_KEY=
```

Both are optional. `app/db.py` and `app/ai_provider.py` each expose an `is_configured()`-style check and degrade gracefully, mirroring each other.

`start.bat`: activate `.venv`, run `uvicorn app.main:app --reload` on `127.0.0.1:8000`, and open `http://localhost:8000` in the default browser. If the venv is missing, print a plain-English message telling him what to run instead of failing cryptically.

## 8. Data and MySQL

### 8.1 Data pipeline (same as v1, plus one MySQL step)

1. `scripts/download_data.py` — one-time download of **daily** OHLCV from Yahoo Finance for the five tickers in `app/stocks.py` (`MARUTI.NS`, `RELIANCE.NS`, `INFY.NS`, `HDFCBANK.NS`, `BAJAJ-AUTO.NS`, display names Maruti Suzuki, Reliance, Infosys, HDFC Bank, Bajaj Auto), from **2011-01-03 to the present**. Untouched copy to `data/raw/`; cleaned copy (snake_case columns, ascending dates, prices rounded to 2 decimals) to `data/daily/`. Keep **both** `close` and `adj_close`.
2. `scripts/resample_data.py` — derive **weekly** (calendar week ending Friday) and **monthly** (calendar month end) candles **from daily only**. Daily is the single source of truth; Yahoo is never queried twice.
3. `scripts/verify_data.py` — nulls, duplicate dates, ordering, OHLC sanity (low ≤ open/close ≤ high), gaps, and corporate-action ratio-shift detection.
4. **New:** `scripts/setup_db.py` — creates all tables and loads every CSV into MySQL. Idempotent: safe to run twice without duplicating rows (upsert on the unique key, or truncate-and-reload inside a transaction).
5. **New:** `scripts/verify_mysql_load.py` — for every symbol and timeframe, row counts and every value in MySQL match the CSVs exactly.

All indicators and backtests use **adjusted** prices. For charting, scale each candle's open/high/low by `adj_close / close` so candle shapes stay consistent with the adjusted indicators.

### 8.2 Schema (SQLModel classes in `app/models.py`)

Every string column that is indexed or part of a unique key needs an explicit `max_length` (MySQL requires a length for indexed `VARCHAR`). Prices are `DECIMAL(12,2)` in MySQL and converted to `float` when loaded into pandas.

- **`Stock`** — `symbol` (PK, VARCHAR 20), `name`, `exchange` (`NSE`). Seeded from `TICKERS`; `TICKERS` remains the source of truth in code.
- **`PriceBar`** — `id`, `symbol`, `timeframe` (`daily` / `weekly` / `monthly`), `date`, `open`, `high`, `low`, `close`, `adj_close`, `volume`. Unique on `(symbol, timeframe, date)`, index on `(symbol, timeframe)`.
- **`WatchlistItem`** — `id`, `user_id` (default `DEFAULT_USER_ID`), `symbol`, `added_at`. Unique on `(user_id, symbol)`.
- **`JournalEntry`** — `id`, `user_id`, `symbol`, `side` (`BUY` / `SELL`), `quantity` (positive int), `price` (positive), `trade_date`, `notes` (optional), `created_at`. These are **real trades the user made**, never mixed with hypothetical backtest trades.
- **`CupConfirmation`** — `id`, `user_id`, `symbol`, `left_rim_date`, `confirmed_at`. Unique on `(user_id, symbol, left_rim_date)`.

Every user-owned table has a real `user_id` column from day one, all defaulting to one shared `DEFAULT_USER_ID`. There is no login screen. Adding accounts later is a data migration, not a schema rewrite.

Tables are created on startup through FastAPI's lifespan handler when the DB is configured.

### 8.3 Reading prices

`app/prices.py` exposes one cached loader, e.g. `load_prices(symbol, timeframe) -> DataFrame`, used by **every** endpoint (no other file reads prices directly):
- If the DB is configured and reachable, read from `PriceBar`; otherwise read `data/<timeframe>/<symbol>.csv`.
- Cache with `@functools.lru_cache` — prices never change at runtime. Callers must never mutate the returned DataFrame (they only build new frames from its columns); check this in every system module before relying on the cache.
- Log once which source is in use.

### 8.4 MySQL setup and access (walk him through it in Phase 2)

**Rule: you never see the database password.** Never read, print or ask for the contents of `.env`, and never ask him to type a password into chat. Phase 0 creates `.claude/settings.json` containing `{"permissions": {"deny": ["Read(./.env)"]}}` — this blocks only `.env` itself; `.env.example` stays readable. Python code and scripts load `.env` themselves through `python-dotenv`. If a connection fails, diagnose from the error message and ask him to check specific non-secret parts (host, port, user name, database name), never the password.

1. **Install.** Download **MySQL Community Server 8.4 LTS**, Windows **MSI**, from dev.mysql.com/downloads. When the MSI finishes, run **MySQL Configurator** straight away (the server won't start until it's configured): config type *Development Computer*, port **3306**, a **root password he writes down**, and configure MySQL as a **Windows service that starts at boot**. Default install folder: `C:\Program Files\MySQL\MySQL Server 8.4\`. MySQL Workbench is optional and a separate download; nothing in the project depends on it.
2. **Put the client tools on PATH.** Walk him through adding `C:\Program Files\MySQL\MySQL Server 8.4\bin` to his user `Path` environment variable, then fully restarting VS Code. Confirm with `mysql --version` in a new terminal.
3. **Create the database and app user — he types this himself.** In a **PowerShell** terminal (interactive password prompts can hang in Git Bash), he runs `mysql -u root -p`, enters the root password, and pastes this SQL with his own chosen app password in place of the placeholder (never use root in `DATABASE_URL`):
   ```sql
   CREATE DATABASE investiq CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   CREATE USER 'investiq_user'@'localhost' IDENTIFIED BY '<his app password>';
   GRANT ALL PRIVILEGES ON investiq.* TO 'investiq_user'@'localhost';
   FLUSH PRIVILEGES;
   ```
   Advise him to pick an app password of **letters and digits only**: characters like `@ : / # %` break the `DATABASE_URL` format unless URL-encoded.

   > **USER OVERRIDE (2026-10-03), do not "correct" it:** Gaurang explicitly chose to use the MySQL **`root`** account for the app and did not create `investiq_user`. His database is named **`investiq_ai`** (not `investiq`). Trade-off explained to him: root can alter every database on that MySQL server (including his unrelated `talent_bridge` one); a dedicated user could only touch this one. Consequences: `DATABASE_URL` uses `root`, and the step-4 login-path uses `--user=root`. His `.env` also still holds unrelated `DB_*` / `SECRET_KEY` lines from another project; leave them alone.
   > **Version note:** the machine already had MySQL **8.0.46** installed (service `MySQL80`, folder `C:\Program Files\MySQL\MySQL Server 8.0\`), not 8.4 LTS. Nothing in the schema depends on 8.4, so 8.0.46 is used.
4. **Give yourself password-free query access.** In PowerShell he runs:
   ```
   mysql_config_editor set --login-path=investiq --host=localhost --user=investiq_user --password
   ```
   and types the app password at the hidden prompt. It is stored in his Windows profile (`.mylogin.cnf`), obfuscated, outside the project. From then on, run every direct SQL check as `mysql --login-path=investiq investiq -e "<SQL>"` — no password on the command line, no prompt. Use this for row-count checks, schema inspection and every "confirm cleanup with a direct query" check in section 15.
5. **`.env`.** He copies `.env.example` to `.env` in VS Code and fills in `DATABASE_URL` himself. Then you run `python scripts/setup_db.py` and `python scripts/verify_mysql_load.py`.
6. **Done when:** `mysql --login-path=investiq investiq -e "SHOW TABLES;"` lists the tables, the verify script passes, and the app still runs with `DATABASE_URL` removed (CSV fallback).

Use `utf8mb4` throughout; explanation text contains em-dashes and `₹`.

## 9. Indicators and RSI readings

- **Moving averages are SIMPLE (SMA) project-wide** unless a system's notes say otherwise. (`ema()` may exist in the library but nothing trades on it.)
- **RSI(14) uses Wilder's original smoothing**, seeded the standard way so values match TradingView/investing.com, including in the early years.
- **Swing points:** N-bar fractal (a bar's high/low must exceed its `n` neighbours on each side), `n=2` default, tunable.
- **RSI zone** (instantaneous, notes page 1): 0–40 bearish, 40–60 sideways, 60–100 bullish.
- **RSI trend** (behavioural, notes page 12): strong zones apply by value alone (60–80 strong uptrend, 20–40 strong downtrend, extended past 80 / below 20). The overlapping 40–60 middle is resolved by RSI direction versus **1 week ago**: rising → Uptrend, falling → Downtrend, within ±0.5 points → Sideways. This 40–60 tiebreak is a constructed rule, not verbatim from the notes; say so in the module docstring.
- Both readings are computed and shown wherever RSI is shown.

## 10. System 1 — Trend Following (authoritative rules)

Evaluated on **completed weekly candles** only, using the **20-period SMA of weekly closes** and **RSI(14)**. "20 DMA" in the notes means 20 *weekly* periods, simple, not exponential — locked after a numeric comparison on real data.

- **Entry (BUY), only when flat:** RSI *crosses* from ≤ 60 to > 60 (`prev_rsi <= 60 and rsi > 60`, a crossover, not a level test) **and** weekly close > 20-SMA.
- **Exit (SELL), only when in a position:** weekly close < 20-SMA. This is both the exit and the trailing stop; there is no separate fixed stop, and RSI plays no part in the exit.
- **States, one per completed weekly bar:** `BUY` (flat, entry met), `HOLD` (in position, close ≥ SMA), `SELL` (in position, close < SMA), `NEUTRAL` (flat, no trigger).
- **`DEVELOPING`** is a flag on `NEUTRAL`: close > SMA and RSI between 50 and 60 and rising.
- Deliberate asymmetry: entry needs close **>** SMA, HOLD needs close **≥** SMA.
- Walk the weekly bars chronologically (stateful, not vectorised).
- **UI copy:** the system is checked on **Mondays** after the prior week's candle closes. Any "current signal" names the week-ending date it refers to and never presents an in-progress week as a completed signal.
- Signals exist only on weekly candles; chart markers show only in the weekly view.
- **UI label and explainer:** "Trend Following," with a short explainer saying it buys strength (RSI above 60) and exits on a trailing 20-week-average stop with no target.

## 11. System 2 — Cup & Handle (authoritative rules)

**Monthly candles. Minimum 5-year cup.** All thresholds are named, tunable module constants (e.g. `RIM_SYMMETRY`, `BOTTOM_DWELL_FRAC`, depth bounds).

**Cup geometry**
- Left rim: local high, highest in a ±3-month window.
- Cup bottom: lowest low after the left rim.
- Right rim: a later local high within **8%** of the left rim's price (strict band, keep as written).
- Duration left rim → right rim ≥ **60 months**.
- Depth: bottom **12–50%** below the left rim.
- Rounded bottom: the lowest quartile of the cup's price range accounts for **≥ 20%** of the cup's duration.

**Handle — required.** A cup without a qualifying handle is not a complete setup; keep checking later right-rim candidates.
- Duration 1–6 months. Retraces **less than ⅓** of cup depth (this also places it in the upper third).

**Entry / stop** relative to the **buy point = the handle's high**:
- Entry = buy point × **1.04**, as a **pending stop order**: triggers only when a later month's high crosses it; entry price is the trigger level itself. No expiry.
- Stop = buy point × **0.76**, fixed at entry.

**Selling ladder — three independent, user-selectable modes** sharing the same entry and stop:
- **Income:** sell ⅓ at +10%, ⅓ at +20%, hold the final ⅓. The original stop stays in force for the whole position for as long as any of it is held; it is never raised.
- **Wealth:** sell ⅓ at +20% and ⅓ at +40%, hold the final ⅓. The stop trails at every +10% milestone to (milestone − 10%), except the first milestone (+10%), which raises the stop to +10% itself. So +10% → stop +10%, +20% → +10%, +30% → +20%, +40% → +30%, … +110% → +100%, repeating indefinitely.
- **Trail:** identical stop ladder to Wealth, no partial sells; the whole position rides until the stop is hit.

**Backtest:** one position at a time per stock; sort trades by entry index before walking chronologically (overlapping cups can resolve out of left-rim order). A multi-tranche trade is collapsed into one blended entry/exit (weighted-average return) so the shared backtest helpers work unchanged; keep per-tranche detail in a `tranches` field for the UI.

**Honesty requirement (hard):** detection is fuzzy and 5-year cups are rare. The UI shows detector output as **"POSSIBLE cup formation — review the chart,"** never as an automatic BUY badge. Entry/stop/ladder figures appear only after a human confirms the cup via **"Confirm this cup,"** which persists a `CupConfirmation`. The confirm endpoint recomputes the current cup server-side and accepts **no request body**.

**Expected real-data result:** v1 found **zero** geometrically valid cups across all five stocks at these thresholds (rim symmetry is almost never met on these strong compounders). That is the correct outcome, not a bug. Do not loosen thresholds to "find" cups. Test the full detection/confirmation/ladder flow with synthetic data and, for the UI, a temporary monkey-patched server process that never edits the module file; delete any test confirmation rows afterwards.

## 12. System 3 — Value Buy (authoritative rules)

**UI label: "Value Buy — technical pullback entry."** It is **not** fundamental value investing (no P/E, no book value); say so visibly and boldly in the UI copy itself, not only in a margin note. Keep it separate from System 1 in code and UI: System 1 buys strength with a trailing stop and no target; Value Buy buys weakness with a fixed stop and a defined target.

**Timeframes:** monthly = context filter; weekly = trigger and execution. Monthly RSI(14) is computed from the daily-derived monthly candles (not re-derived from weekly). Join monthly context to weekly bars as-of, with **no lookahead**: a weekly bar only ever sees an already-closed month.

**Entry, only when flat, one position at a time per stock:**
1. **Context:** monthly RSI between **38 and 45** and **rising** versus the prior month. Falling into the range does not count.
2. **Trigger:** a weekly candle closes green (`close > open`) while context is active — the signal candle.
3. **Execution:** arm a stop-buy at the signal candle's **high**. Entry triggers only when a *later* weekly high trades above it; entry price = the signal candle's high. Model it as a pending stop order. The setup **expires after 2 weeks** untriggered. A new signal candle while armed **re-arms** at the new high and resets the 2-week expiry.

**Exit — bracket, whichever hits first:**
- **Stop:** the signal candle's **low**, fixed, never trails.
- **Target:** the **highest-value** swing high (high exceeds both immediate neighbours) within the prior **20 weekly bars** (lookback is a parameter). If that target is at or below the entry price, skip the entry and keep the setup armed.
- The all-time high is shown as secondary context only.

**Risk-reward**, a fixed snapshot at entry: `risk = entry − stop`, `reward = target − entry`, `ratio = reward / risk`.

**States:** NEUTRAL / ARMED / BUY / HOLD / SELL (exit reason: stop or target).

Split the weekly loop into its own function (e.g. `run_weekly_state_machine(ohlc, context, swing_lookback)`) so it can be tested with a hand-built context series.

**Expected real-data result:** Bajaj Auto has zero Value Buy trades over the full history (its monthly RSI only ever *fell* into the zone). Correct, not a bug.

## 13. Product features and UX (all carried from v1)

### Backtests (all money hypothetical — say so on every backtest view)
- Capital is a user input (default ₹1,00,000), validated: non-positive values show an explicit message.
- Capital **compounds trade-to-trade** per stock; sits flat while not in a position. No transaction costs. An open position at the end of the data is marked to market and shown separately from closed-trade stats.
- Shared helpers `compound_equity_curve()` and `summarize()` in `backtest.py` are used by all systems, so compounding rules are identical everywhere.
- Every backtest reports total return, **maximum drawdown**, **longest losing streak**, and a **buy-and-hold benchmark over the identical period**, shown right beside the strategy return. v1's honest finding was that Trend Following underperformed buy-and-hold on all five stocks; report whatever the data shows, plainly.
- `/portfolio`: total capital split equally across the five stocks for System 1, independent per-stock equity curves summed, never reallocated between stocks.
- Trade returns coloured green/oxblood, each with a shape or sign so colour is never the only cue.

### Margin notes (`app/explanations.py`)
Deterministic, template-based 1–2 sentence explanations for RSI zone, RSI trend, each system's signal state, and each backtest summary. This rule-based engine guarantees an explanation for every selection without the LLM. Every label a system can produce has a matching template (verify exhaustively).

### AI chat (`app/ai_provider.py`, `app/ai_context.py`)
- One chat box per stock page, scoped to that stock. Multi-turn but **stateless server-side**: the browser keeps the history in a JS array and resends it each request. Nothing is persisted.
- `build_context()` assembles a plain-text snapshot from already-computed values only: latest weekly close, 20-week SMA, RSI with zone and trend, System 1 state, Value Buy state, and both systems' backtest summaries **including the buy-and-hold comparison**. Never raw price series.
- System prompt rules: answer only from the given data; never fabricate a number; decline buy/sell/hold advice under any phrasing; say plainly when something is outside the data (including any stock other than the five); reply in **plain prose with no markdown**.
- `POST /api/stocks/{symbol}/ask` always returns HTTP 200 with `{"reply": …, "error": null}` or `{"reply": null, "error": "…"}`. `AIUnavailableError` covers both "no key" and provider failures.
- UI: the user's lines in ink/serif labelled "You"; AI lines in brass/Plex Sans labelled "AI"; hairline rules between turns.

### Watchlist, journal, holdings
- Watchlist rows show each stock's current System 1 state (with DEVELOPING) and Value Buy state, reusing existing computation. DEVELOPING and ARMED are emphasised. A watchlist toggle button also sits on each stock page.
- Journal: form + table, server-side validation (known symbol, positive quantity and price, BUY/SELL).
- **Holdings** (`portfolio_holdings.compute_holdings(entries, current_prices, names)`, pure computation): **FIFO** cost basis (earliest shares sold first, as Indian tax law computes equity gains). Sort entries by `trade_date`, not insertion order. A SELL larger than the current holding is capped and reported in an `inconsistencies` list. Shows remaining quantity, average cost, realised and unrealised P&L. "Current price" is the latest weekly close, and the UI states its as-of date plainly (prices are a one-time download, never live). Section "Your holdings" sits above the add-entry form and reloads after every add/delete.
- Worked check: BUY 10 @ 100, BUY 5 @ 120, SELL 8 → remaining 2 @ 100 + 5 @ 120, average cost 800 / 7 = 114.29.

### Screener (`/screener`)
One table, all five stocks from a single `GET /api/screener`: latest weekly close, RSI zone, RSI trend, System 1 state (+ developing), Value Buy state. Client-side dropdown filters on each state column; System 1's filter has a synthetic DEVELOPING option. Empty-state row when no stock matches.

### Position size calculator (client-side, `position_size.js`)
`shares = floor((capital × risk%) / (entry − stop))`, capped so position value never exceeds capital. Pre-fills entry from the latest weekly close and stop from the 20-week SMA. Recalculates on every keystroke, shows its working, and handles stop ≥ entry, zero shares, and negative inputs with clear messages. Explicitly "arithmetic, not a recommendation." Check: ₹1,00,000 at 2%, entry 100, stop 90 → 200 shares, ₹20,000.

### Stock page (top to bottom)
1. "Where <stock> stands today" — one colour-and-shape-coded line per system with a short factual descriptor, using data the page already fetches (no extra requests). Cup & Handle keeps its quiet styling. Rows fall back to plain text on short history or load failure.
2. Chart: candlesticks + 20-week SMA + synced RSI pane, daily/weekly/monthly switcher. Opens on a recent window (`DEFAULT_BARS_VISIBLE`: 250 daily, 156 weekly, 120 monthly), full history one zoom-out away. System 1 markers are arrows **without text labels**, with a **"Show trade markers"** toggle. A **legend** names the arrows, the 20-week average line and the filled/hollow candle convention.
3. System 1 section (explainer, current signal, margin notes, backtest, trade log, equity curve).
4. Value Buy section (bold "not fundamental" clarification, signal, stop/target/risk-reward columns, backtest).
5. Cup & Handle section (POSSIBLE / confirm flow, ladder mode dropdown switching which backtest is shown).
6. Position size calculator. 7. AI chat. 8. Watchlist toggle.

### Home page
Hero stating the philosophy in prose; a live tile grid of all five stocks (price, Trend Following state, Value Buy state) filled from `/api/screener`; an "Explore" grid linking Screener / Portfolio / Watchlist / Journal with one-line descriptions. Tiles are ruled cells divided by hairlines, not cards.

### Site-wide UX rules
- **Disclaimer footer on every page:** educational project, not financial advice, not a recommendation to buy or sell.
- **Errors:** an `HTTPException` handler returns JSON for `/api/*` (frontend relies on `data.detail`) and a styled `error.html` for page routes. Every frontend `fetch` is wrapped in `try/catch`; no page or button is ever left stuck on "Loading…" or "Adding…". `#page-error` element on the stock page.
- **Writes:** every button that writes to the database shows "Adding… / Removing… / Updating… / Deleting…" while in flight.
- **Caching:** every GET of data that can change after a write (`/api/watchlist`, `/api/journal`, `/api/journal/holdings`, cup status) uses `fetch(…, {cache: "no-store"})`. Static files get `Cache-Control: no-cache` via middleware scoped to `/static/`.
- **Skeleton loading states** shaped like the content (`.skeleton`, `.skeleton-text`, `.skeleton-chart`, `.skeleton-row`; a `skeleton_rows()` macro). Text and table skeletons are server-rendered; chart skeletons are removed with an explicit `hideSkeleton()` in a `finally`. The chart skeleton overlay needs `z-index: 100` to sit above the chart canvas.
- **Empty states** for every trade table, system-specific (e.g. "No Value Buy setups occurred in this stock's history.").
- **Splash cover** (`splash.js`, `splash_cover()` macro) on the data-loading pages and the home page: an InvestIQ title cover that lifts when no fetch is in flight (hold each request until its body has fully downloaded) **and** no `.skeleton` remains visible. Stall detection lifts it ~2.5 s after the page stops changing when requests have settled but skeletons remain. Three escape hatches so it can never strand a visitor: `<noscript>` CSS, an inline timer (35 s) that runs even if `splash.js` fails to load, and `splash.js`'s own failsafe (25 s, always shorter than the inline one).
- **First-visit orientation note** on stock pages pointing to the Screener, rendered `hidden` and revealed by JS, dismissed permanently via `localStorage`; if storage is unavailable, show the note rather than throw.
- **Social metadata:** per-page Open Graph + Twitter `summary_large_image` tags via a `social_meta()` macro and a 1200×630 `og-image.png` rendered from the site's own CSS and fonts. Build `og:url`/`og:image` from the incoming request (absolute URLs, `https` behind a proxy), never hard-coded. The error page gets no preview, only `noindex`.
- **Mobile:** at 375 px no page scrolls sideways. Wide tables sit in a `.table-scroll` (`overflow-x: auto`) wrapper. Charts sit outside the `.ledger-layout` grid, full width, never inside a grid item.

## 14. Design system — "The Ledger"

A printed financial record annotated by hand, echoing the user's handwritten notebook.

- **Palette:** paper `#f5f1e6`, ink `#1a1a1a`, brass `#a6763d`, forest green (up) `#1e5631`, oxblood (down) `#4a0e0e`, hairline `rgba(26,26,26,0.18)`.
- **No drop shadows, no floating cards, no dark mode.** Hairline rules only; paper doesn't have shadows.
- **Typography:** Plex Serif for prose; Plex Mono for figures (`.figure`, `font-variant-numeric: tabular-nums`); Plex Sans for margin notes.
- **Computed vs interpreted:** computed values in ink in the main column. Every explanation and AI line lives in a right-hand `.margin-note` (Plex Sans, brass, indented). `.ledger-layout` is a two-column grid used once per annotated section; under 720 px it collapses and each note sits directly beneath the figure it annotates, keeping its brass and indent.
- **Colourblind safety:** forest and oxblood collapse under deuteranopia, so colour never carries meaning alone. Candles: **filled body = up, hollow oxblood-outline body = down**. Signal states pair colour with a shape: BUY ▲ and HOLD ● in forest, SELL ▼ in oxblood, ARMED / DEVELOPING ◆ in bold ink, NEUTRAL · in plain ink. **Brass is never used for a computed state** — it is reserved for the margin/AI voice. Centralise this in `app/static/js/signal_style.js` (`signalStateMarkup`, `summaryStateMarkup`) so a state looks identical on every page.

## 15. Verification standards (apply to every phase)

- Every calculation module (`indicators`, `trend_following`, `value_buy`, `cup_pattern`, `backtest`, `portfolio_holdings`) gets a `scripts/verify_*.py` that cross-checks production code against an **independent from-scratch reimplementation** on all five stocks (exact match expected), plus invariants and **hand-built synthetic scenarios**.
- Watch for v1's known traps in verification scripts themselves: pandas 3.x converts `None` to `NaN` in string columns; synthetic price fixtures with net drift can push RSI past a threshold before the SMA window opens; off-by-one when a simulator starts at `entry_idx + 1`.
- UI phases are verified with Playwright (installed temporarily) at desktop and 375 px: zero console errors, zero horizontal overflow measured via `document.documentElement.scrollWidth`, and screenshots inspected. A test that "passes" because there was nothing to click is not a pass.
- AI behaviour is verified with **real API calls**, never mocks: grounded numbers match computed values exactly, the advice refusal holds across several phrasings, an off-list stock is refused, multi-turn context works, and replies contain no markdown.
- Graceful degradation is verified by actually removing `GEMINI_API_KEY` and `DATABASE_URL` and confirming every other route still returns 200.
- Any test data written to MySQL is deleted afterwards, and the cleanup is **confirmed with a direct query**, never by trusting the test's own report.
- When a check fails, find out whether the bug is in the product or in the test before changing anything.

## 16. Build phases

Each phase ends with: verification passing, a short report to the user, a suggested commit message, and a wait for "continue."

| # | Phase | Done when |
|---|---|---|
| 0 | **Foundation** — check Python, create `.venv`, install FastAPI/Uvicorn/Jinja2, `.gitignore`, `.claude/settings.json` (deny reading `.env`, section 8.4), `start.bat`, minimal `app/main.py` + home template, `CLAUDE.md`, move v1 files into `docs/v1/`, `git init`, walk him through creating a private GitHub repo and pushing | Double-clicking `start.bat` opens a working page |
| 1 | **Data pipeline** — `stocks.py`, download, resample, verify (section 8.1 steps 1–3) | Five stocks verified; two values spot-checked against Google Finance with him |
| 2 | **MySQL** — guide the install (8.4), `db.py`, `models.py`, `setup_db.py`, `verify_mysql_load.py`, `prices.py` with CSV fallback | MySQL matches CSVs exactly; app runs with and without `DATABASE_URL` |
| 3 | **Indicator engine** — `indicators.py`, `rsi_zones.py`, `verify_indicators.py` | Exact match against independent reimplementation |
| 4 | **Charts + Ledger** — fonts, vendored chart library, `style.css`, stock page, candles endpoint, chart with SMA + RSI pane, legend, recent-window default | Screenshots at desktop and 375 px; colourblind conventions visible |
| 5 | **System 1** — state machine, endpoint, markers (no labels, toggle), current signal with week-ending date and Monday copy, explainer | Verify script passes; markers land on SMA crossings |
| 6 | **Backtest engine** — shared helpers, System 1 backtest with drawdown/streak/buy-and-hold, `/portfolio` | Verify script passes; honest results displayed |
| 7 | **Margin notes** — `explanations.py`, per-section notes, exhaustiveness check | Every label has a note; wording read through with him |
| 8 | **System 3 — Value Buy** | Verify script passes, including the six scenarios (happy path, 2-week expiry, re-arm, stop exit, one position at a time, context required) |
| 9 | **AI layer** — walk him through getting a Gemini key; provider, context, endpoint, chat UI | Real-call checks in section 15 pass; works without a key |
| 10 | **Watchlist + journal + holdings** | Full CRUD against real MySQL, FIFO worked check, data survives restart, cleanup confirmed by query |
| 11 | **Screener + home page** | Filters work, empty state shows, home tiles show real states |
| 12 | **System 2 — Cup & Handle** — detector, ladders, backtest, `CupConfirmation`, UI | Real data shows "no possible cup" everywhere; synthetic and monkey-patched flows pass |
| 13 | **Polish + full sweep** — every item in section 13's site-wide UX rules, position calculator, error page, OG image; rewrite `README.md` and update `PRESENTING.md` for the new hosting | Every page and interactive element checked; every verify script re-run |

## 17. Progress tracker

Keep this current. Show it at the start of every session.

| # | Phase | Status | Notes |
|---|---|---|---|
| 0 | Foundation | Done | Code built, server returns 200. `.claude/settings.json` (deny Read .env) added late, on 2026-10-03. start.bat double-click test PASSED (user screenshot, 2026-10-03: browser opened localhost:8000 with the app's page; start.bat's server command re-verified by Claude on current code). First commit made 2026-10-04 (19d4547, 100 files, .env excluded). Pushed 2026-10-04 to private repo https://github.com/gs2246/InvestIQ---AI (remote `origin`, branch `main`; verified identical, no .env) |
| 1 | Data pipeline | Done (spot-check unconfirmed) | verify_data.py passes on all 5. 3,889 daily rows each (2011-01-03 to 2026-10-01), 822 weekly, 190 monthly. User said "continue" without confirming the Google Finance values (Maruti 1 Oct 2026 close 11,386.00; Infosys 1,035.00) |
| 2 | MySQL | Done | MySQL 8.0.46 (service MySQL80, Auto start), root + db `investiq_ai` (user override, see 8.4). Login-path `investiq` set; query with `"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe" --login-path=investiq investiq_ai -e "<SQL>"` (mysql is not on PATH). 24,505 price rows; verify_mysql_load.py passes (171,535 values identical); setup_db.py run twice, 0 duplicates; app runs with and without DATABASE_URL |
| 3 | Indicator engine | Done (TradingView spot-check pending) | indicators.py (sma, ema, rsi, swing_points), rsi_zones.py (zone, trend, 5 trend labels). verify_indicators.py: 4,665 checks pass; RSI/EMA exact vs plain-Python reimplementation, SMA within 4e-12. Boundary choice: exactly 40 and 60 are Sideways (Bullish = RSI > 60). "1 week ago" = 1 weekly bar / 5 daily bars; trend undefined for monthly. Latest weekly RSI(14) for the user to check on TradingView: Maruti 29.91 (w/e 2026-10-02) |
| 4 | Charts + Ledger | Done | Fonts (6 Plex woff2 + OFL licence), lightweight-charts 4.2.3 vendored, style.css, base/home/stock templates, `GET /stock/{symbol}`, `GET /api/stocks/{symbol}/candles`. Playwright (desktop 1280 + 375 px): 111 checks, 0 console errors, 0 overflow, 0 external requests; screenshots inspected. Chart line = 20-period SMA of the timeframe shown, legend names it (20-day/week/month). Margin note on the stock page is a static placeholder until Phase 7. Carry forward: (a) Plex has no ▲▼●◆ glyphs, so Phase 5 signal shapes must be SVG/CSS; (b) last monthly bar (Oct 2026) holds only 1 Oct but is labelled 2026-10-31, and "completed week/month" needs a rule, plan: download_data.py writes data/meta.json with the download date; (c) brass #a6763d on paper is ~3.4:1 contrast, below the 4.5:1 guideline for small text; palette is spec'd so left as is |
| 5 | System 1 | Done | trend_following.py (run_state_machine + evaluate/signals/current_signal), `GET /api/stocks/{symbol}/system1`, signal_style.js (SVG shapes), system1.js, markers (arrows, no text, weekly only, toggle), Monday copy. Completed-bar rule: data/meta.json `downloaded_on`; a bar is complete if its label date < that date (`prices.load_completed_prices`). Boundary choices: DEVELOPING's "50 to 60" inclusive, "rising" strictly. verify_trend_following.py: 12,433 checks; mutation tests caught all 3 sabotaged rules (level-entry and strict-hold caught only by hand scenarios). Browser: 96 checks, 0 errors, screenshots inspected (arrows on SMA crossings). Current: Bajaj Auto SELL (w/e 2026-10-02), others NEUTRAL. Cosmetic for Phase 13: RSI value label can overlap the 40/60 axis labels |
| 6 | Backtest engine | Done | backtest.py (compound_equity_curve, summarize, max_drawdown, longest_losing_streak, buy_hold_curve, trade_rows, validate_capital); System 1 backtest + portfolio in trend_following.py; `GET /api/stocks/{symbol}/backtest?capital=`, `GET /api/portfolio/backtest?capital=`, `/portfolio` page; backtest_view.js (shared UI), system1_backtest.js, portfolio.js. **USER DECISION (2026-10-03): System 1 fills at the adjusted close of the signal week** (BUY close in, SELL close out), not next Monday's open. Backtest period = first evaluable week to newest completed week, same for buy-and-hold. verify_backtest.py: 226 checks (equity matches independent rebuild to ~1e-15 relative). Browser: 82 checks, screenshots inspected. Honest result: Trend Following underperformed buy-and-hold on all five (e.g. Maruti +243.9% vs +960.0%; Reliance -14.2% vs +514.9%; portfolio +100.9% vs +689.3%) |
| 7 | Margin notes | Done (user replied "ok" to the wording, 2026-10-03) | explanations.py (ZONE/TREND/SYSTEM1/BACKTEST templates keyed by label), formatting.py (format_inr, format_pct); notes in /api/.../system1, /backtest, /portfolio/backtest and server-rendered RSI notes; placeholder note removed. verify_explanations.py: 19,148 checks (exhaustive label coverage, ≤2 sentences, no markdown, no advice wording, real figures quoted). Browser: 58 checks, notes brass, beside on desktop / beneath+indented at 375 px. Value Buy and Cup notes come with Phases 8 and 12 |
| 8 | System 3 — Value Buy | Done (choices await user's OK) | value_buy.py (is_context_active, monthly_context, join_context, swing_target, run_weekly_state_machine, evaluate, current_signal, backtest), `GET /api/stocks/{symbol}/value-buy?capital=`, VALUE_BUY_NOTES (SELL split stop/target), value_buy.js, stock-page section with bold "not fundamental" line. Choices made where notes are silent (documented in module docstring): as-of join uses months ending on/before the week's Friday; 38-45 inclusive; target looked up at trigger time from weeks i-20..i-2 (swing needs next week to confirm); exits fill at stop/target level; stop first if both hit in one week; exits checked from the week after entry; adjusted OHLC. verify_value_buy.py: 4,209 checks incl. all six required scenarios; mutation tests caught 3/3 (lookahead swing only by hand scenario). Browser: 68 checks (ARMED/HOLD/SELL fed in). Real: Bajaj Auto 0 trades (RSI entered 38-45 twice, both falling); all others trail buy-and-hold (Maruti +67.7% vs +905.4%, Reliance +16.7% vs +681.5%, Infosys +1.5% vs +393.1%, HDFC Bank -3.1% vs +512.6%). All five NEUTRAL today |
| 9 | AI layer | Done | SDK checked: `google-genai` 2.28.0 is current (old `google-generativeai` stalled at 0.8.6); pinned. ai_provider.py (GeminiProvider, AIUnavailableError, to_plain_prose safety net, tool calling disabled), ai_context.py (build_context from computed values only + SYSTEM_PROMPT), `POST /api/stocks/{symbol}/ask` (always 200), chat.js + chat section. scripts/verify_ai.py (REAL calls, ~17 per run; needs running app): 64 checks: every quoted number is in the given data, 6 advice phrasings refused, TCS/Nifty/Bitcoin refused by name, multi-turn uses history, no markdown even in raw model output. Verification led to two prompt fixes (no "data you have" echo; model sentence for off-list assets). Browser: 34 checks (real replies via the page, Asking… state, failure recovery, no-key page). No-key path: all routes 200 |
| 10 | Watchlist + journal + holdings | Done | portfolio_holdings.py (FIFO; same-date BUY before SELL; capped SELLs reported in plain words; `shares_bought`), watchlist/journal/holdings API (`/api/watchlist`, `/api/journal`, `/api/journal/holdings`; 503 without DB; server-side validation with 13 rejection cases), `/watchlist`, `/journal`, stock-page toggle, header nav, api.js (no-store GETs, busy labels). verify_portfolio_holdings.py: worked check (2@100 + 5@120, avg 114.29) + 2,000 random journals vs share-by-share reference. Real MySQL CRUD: add/duplicate/remove, data survives restart, cleanup confirmed by direct query (0 rows). Browser: 56 checks. Bugs found: (1) SQLModel 0.0.47 rejects naive datetimes, so `_utcnow` is now tz-aware UTC (would also have broken CupConfirmation); (2) a visually-hidden table header widened the journal to 640 px on phones; `.table-scroll` now `position: relative`. Verification lessons: phone checks must assert `innerWidth == 375` (scrollWidth<=clientWidth passes even when the page is zoomed out; all 9 pages re-audited OK); venv python.exe is a launcher, so stop servers by process tree |
| 11 | Screener + home | Done | `GET /api/screener` (screener_row reuses latest_weekly_reading + current_states; both now lru_cached with copies handed out: 0.7 s -> 0.004 s), `/screener` with 4 dropdown filters (System 1 has synthetic DEVELOPING) + empty-state row + Clear filters, home hero + live tiles (ruled cells) + Explore grid, nav gains Screener. Fixed: latest_weekly_reading now uses completed bars. API consistency: 41 checks vs fresh module output. Browser: 80 checks (13 filter combinations, DEVELOPING fed in, tile layout, empty-state message stays on screen at 375 px, strict width) |
| 12 | System 2 — Cup & Handle | Done (choices await user's OK) | cup_pattern.py (local_highs, detect_cups, find_entry, simulate income/wealth/trail, blend, trades_for_mode, backtest, current_status), `GET /api/stocks/{symbol}/cup-pattern?capital=` (levels only if confirmed), `POST .../cup-pattern/confirm` (no body, recomputes; 409 no cup, 503 no DB), CUP_NOTES, cup.js + stock-page section (quiet styling, ladder dropdown). **USER DECISION (2026-10-04): the handle ends at the first month whose high regains the right rim; buy point = highest high inside the handle.** Choices where the notes are silent (in module docstring): rounded bottom uses monthly closes; stop-buy fills only after the rim is confirmed (r+3) and the regain month exists; stop checked first inside a month, stop raises apply next month, exits from the month after entry; fills at exact levels. Real data: 0 cups on all five; no 60-month rim pair within 8% (right rims overshoot by +37% to +1,262%). verify_cup_pattern.py: 63 checks (independent detector identical at strict and loosened test thresholds, 24 loosened cups; 91-month hand-built series; ladders by hand; ordering); 3/3 sabotages caught. API: 31 checks on normal, patched (in-memory loosened) and no-DB servers. Browser: 114 checks. Fixes from screenshots: monthly wording (months / month ending), blended-trade equity disclosure, ladder phrasing. Test confirmation rows deleted; direct query: 0 rows. adjusted_ohlc moved to prices.py (shared with Value Buy; re-verified) |
| 13 | Polish + sweep | Done | Error handlers (JSON `detail` sentence for /api/* incl. 404/405/422/500; styled error.html with noindex, no preview), `_macros.html` (social_meta, skeleton_rows, splash_cover), base.html blocks (description read via self.description(), splash), splash.js (fetch tracking until body downloaded, skeleton check, 2.5 s stall, 25 s failsafe; inline 35 s timer; noscript), skeletons on every page (chart skeleton z-index 100, hideSkeleton in finally), first-visit note (localStorage, storage-blocked fallback), "Where <stock> stands today" (InvestIQ.publish, no extra requests, plain-text fallback), position_size.js (worked check 200 shares / ₹20,000; cap, zero, invalid), RSI 40/60 axis labels removed, og-image.png (site fonts, same-origin render), README.md rewritten, PRESENTING.md updated. Checks: HTTP 117, sweep 114 (all 10 pages x 2 sizes, strict width, splash escape hatches timed: stall 4.2 s, failsafe 25.7 s, inline 35.5 s), degradation 50/50 routes 200 with no key and no DB + 8 DB routes plain message, all 10 verify scripts pass (incl. verify_ai real calls). DB user tables 0 rows by direct query |

**Blockers:** none yet.

**Session log** (append one line per session: date, what was done, what's next):
- 2026-10-03: Phase 0 built (venv on Python 3.14.6, FastAPI/Uvicorn/Jinja2, .gitignore, .env.example, start.bat, minimal app, v1 docs moved to docs/v1/, git init). Next: user double-clicks start.bat, first commit, private GitHub repo + push.
- 2026-10-03: Phase 1 built (stocks.py, download/resample/verify scripts, data/ CSVs). Phase 0 still has open items (start.bat double-click test, commit, GitHub push). Next: Google Finance spot-check, then commit.
- 2026-10-03: Phase 2 code written (db.py, models.py, prices.py, setup_db.py, verify_mysql_load.py, lifespan in main.py). Found MySQL 8.0 already installed. Next: user starts MySQL80 service (admin), creates DB/user, makes .env; then load + verify.
- 2026-10-03: BUILD.md was revised mid-session (8.4 LTS, "never see the password", .claude/settings.json, login-path). Claude had already read .env and seen DB_PASSWORD before noticing; stopped, added settings.json, recorded the root/investiq_ai override. Next: start service, root login-path, create DB, load + verify.
- 2026-10-03: Phase 2 finished and verified (see tracker). Fixed a real bug found by verification: prices.py returned datetime64[s] from MySQL but [us] from CSV; now pinned to [us]. To test "no DATABASE_URL" on Windows set the env var to a single space (empty string deletes it, so .env would load). Next: Phase 3, after user says continue. Still open: Phase 0 (start.bat test, commit, GitHub) and Phase 1 spot-check.
- 2026-10-03: Phase 3 finished and verified. Two real findings: rsi_zones label series lost None to NaN (pandas 3 string inference; fixed with explicit dtype=object); EMA seed summed in numpy order gave 1e-13 differences, now plain left-to-right sum. Next: Phase 4 (charts + Ledger) after user says continue.
- 2026-10-03: Phase 4 finished and verified (see tracker). Playwright, fontTools, brotli uninstalled and the 700 MB Chromium folder deleted; requirements.txt unchanged. Added base.html (not in the layout list) as the shared page frame. Next: Phase 5 (System 1) after user says continue; first settle the completed-bar rule (data/meta.json).
- 2026-10-03: Phase 5 finished and verified (see tracker). start.bat test passed (Phase 0). Playwright and Chromium removed again. Next: Phase 6 (backtest engine + /portfolio) after user says continue.
- 2026-10-03: Phase 6 finished and verified. Fixes found by verification: entry-bar equity wobbled ~1e-11 (ratio now computed first); mobile hid the buy-and-hold column (now fits at 375 px); mobile equity chart cut off early years (minBarSpacing). Playwright/Chromium removed. Next: Phase 7 (margin notes) after user says continue.
- 2026-10-03: Phase 7 built and verified; verification made the NEUTRAL note quote the close. Waiting on: user reads the note wording (done-when for Phase 7). Next: Phase 8 (Value Buy).
- 2026-10-03: Phase 7 wording accepted ("ok"). Phase 8 built and verified (see tracker); implementation choices listed for the user to confirm. Next: Phase 9 (AI layer; user needs a Gemini key) after user says continue.
- 2026-10-03: Phase 9 code built; no-key path verified. Waiting on: user adds GEMINI_API_KEY to .env (never into chat). Then real-call verification.
- 2026-10-03: Phase 9 finished with real Gemini calls (see tracker). Lesson: restart the test server after editing the prompt (uvicorn without --reload keeps old code). Next: Phase 10 (watchlist, journal, holdings) after user says continue.
- 2026-10-03: Phase 10 finished and verified (see tracker). MySQL user tables confirmed empty by direct query. Next: Phase 11 (screener + home page) after user says continue.
- 2026-10-03: Phase 11 finished and verified (see tracker). Next: Phase 12 (System 2, Cup & Handle) after user says continue.
- 2026-10-04: Phase 12 finished and verified (see tracker). Git still has no commits (everything untracked). Next: Phase 13 (polish + full sweep) after user says continue.
- 2026-10-04: Phase 13 finished and verified (see tracker). All phases built. Pushed to private GitHub repo gs2246/InvestIQ---AI (Phase 0 done). Still open: user kept start.bat as the only launcher (no background app.py); login page idea deferred to a possible v2.1; user confirmations: Google Finance spot-check (P1), TradingView RSI (P3), DEVELOPING bounds (P5), Value Buy choices (P8), Cup & Handle choices (P12).
