# InvestIQ AI — Project Context

An AI-powered investment research platform for Indian NSE-listed equities, for beginner–intermediate investors. Started 2026-07-30. This file is the source of truth for continuing the project across sessions — read it fully before doing anything.

## Core philosophy

**"Algorithms calculate. AI explains."** All technical indicators are computed with standard deterministic financial algorithms. AI is used ONLY to interpret those results in plain language — it never calculates, never touches raw data, and physically cannot fabricate a number because it only ever receives already-computed results. Not a price predictor, trading bot, or financial advisor. Every number traces back to real historical data. The UI must make "computed by algorithm" vs "interpreted by AI" visually obvious at a glance — this is a hard design requirement, not a nice-to-have.

Intellectual core: three rule-based trading systems from the user's own handwritten notes (Trend Following on RSI + 20-period MA on weekly candles; Cup & Handle pattern; Value Buy multi-timeframe). Seed data: Maruti Suzuki, Reliance, Infosys, HDFC Bank, Bajaj Auto — ~15 years of history.

Features: interactive price charts, technical indicators, BUY/SELL/NEUTRAL signals, AI explanations, backtesting, position sizing calculator, stock screener, watchlist, investment journal.

## Hard constraints — non-negotiable

- **No Docker, ever.** Not on the user's machine, not suggested as an alternative. Everything runs natively on Windows 11. (Hosting platforms that build the app inside a container on *their* servers are fine — the user never touches Docker themselves. The line is: nothing the user has to install or run locally.)
- **Single-command startup.** The whole app starts by double-clicking `start.bat`. No manual terminal juggling, ever.
- **Never store secrets in code.** Environment files only (`.env`, gitignored), never committed.

## Who the user is

Beginner-level coding experience. Explain terminal commands and tools clearly — never assume prior knowledge of a command, flag, or concept before using it. They ARE the authority on the finance/domain content (the trading systems are from their own notes) — treat them as expert there, beginner on engineering.

## How to work with this user

- **One task at a time, one file at a time.**
- **Explain the why before the what before the code.**
- **Test and verify each phase works before advancing** — never move forward on a broken state.
- **Present technical decisions as options with trade-offs, never assume.** Describe what each option does and why you'd pick one, rather than asking the user to name technologies they may not know.
- **Suggest a Git commit message whenever a feature is complete.**
- **At the start of every session, show a progress tracker**: what's complete, in progress, remaining, and any blockers. See the Progress section below — keep it updated as you work, since it's the mechanism for cross-session continuity.

## Decisions already made (do not re-litigate without reason)

**Environment.** Windows 11, no WSL — native only. Project lives at `C:\Users\gsaha\Projects\investiq` (no spaces in path, outside OneDrive-synced folders). Python 3.14.6 in a `.venv` virtual environment — always activate it first (this also sidesteps the Windows Store fake-python problem, since the venv's `python.exe` takes priority once activated). Git repo, pushed to private GitHub at `github.com/gs2246/Investiq---ai`, branch `main`.

**Stack.**
- Web framework: **FastAPI** (user's explicit choice over recommended Flask — reasoning given: the project needs many JSON endpoints for charts/backtests/AI responses, and FastAPI's type-hint validation pays off there). Templating via Jinja2, static files served by FastAPI's `StaticFiles`.
- Interface approach: Python server + hand-built HTML/CSS pages (no separate frontend framework, no Streamlit — Streamlit was rejected because it can't achieve a distinctive visual identity, which is a hard requirement).
- Charts: **TradingView Lightweight Charts** (free, professional trading-terminal look, not the generic data-science-notebook look of Plotly).
- Data storage: price history as files committed to the project (data doesn't change, no need for a database); a small free cloud database for the watchlist and journal (the only things that get written to, built Phase 10). A single-file database was rejected because most free hosts wipe local disk on restart.
  - Provider: **Neon** (free-tier Postgres) — chosen over Supabase (bundled auth wasn't needed yet) and explicitly **not** Render's own free Postgres, which deletes the database after 30 days unless upgraded (confirmed via research 2026-08-01, before committing to a provider).
  - Library: **SQLModel** (combines the DB table definition and the API schema in one class; maintained by FastAPI's own creator).
  - User model: every table has a real `user_id` column from day one, but the whole app currently runs on one shared `DEFAULT_USER_ID` — there's no login screen yet. This satisfies the "concept of user before login exists" requirement from day one without building auth prematurely; adding real per-person accounts later is a data migration, not a schema rewrite.
  - **Free-tier reality (not a bug, an accepted trade-off):** each database round trip can take 1-3+ seconds, since Neon's serverless compute scales to zero when idle and each request opens a fresh connection. Every button that writes to the database shows an explicit "Updating…/Adding…/Removing…/Deleting…" state rather than appearing unresponsive — this UX pattern is now the standard for any future database-backed feature, not just Phase 10's.
  - GET endpoints for watchlist/journal must be fetched with `cache: "no-store"` — the browser's default HTTP cache will otherwise serve stale data after a write, a real bug caught during Phase 10's own verification.
- Data source: Yahoo Finance, downloaded **once** as **daily** candles (weekly/monthly derived from daily — single source of truth), committed to the project. A live "refresh" button is a nice-to-have, not load-bearing — the site must never depend on Yahoo being up. Store both adjusted and unadjusted prices; compute all indicators/backtests on **adjusted** prices (handles stock splits/bonus issues correctly). The user's handwritten Maruti backtest table used unadjusted screen prices, so re-computed numbers will be recognizably the same trades but different rupee figures — already explained to and accepted by the user.
- AI layer: a deterministic **rule-based explanation engine** is the backbone (free, offline, guaranteed complete for every selection, cannot fabricate numbers) — this is what actually satisfies "mandatory, complete information for every selection." A thin genuine LLM layer sits on top for open-ended conversational Q&A (built Phase 9), satisfying the user's assignment requirement to demonstrably use AI. Local/on-device models are ruled out by hardware (Ryzen 3 5300U, integrated graphics only — too slow). Provider: Google Gemini free tier, accessed through a swappable one-file provider interface (`app/ai_provider.py`) so switching providers later is a one-file change. **The app must work fully with the AI unavailable** — verified Phase 9: every other endpoint returns 200 with no API key configured, only the chat shows a clear "AI is not configured" message.
  - Model: **`gemini-flash-latest`** — a generic alias Google keeps pointed at their current recommended flash model, not a dated snapshot name. Chosen after a pinned snapshot (`gemini-2.5-flash`) turned out to already be deprecated ("no longer available to new users") during this phase's own setup, 2026-08-01 — a live lesson in why aliases beat pinned model names for a hobby project nobody will remember to update.
  - Context fed to the AI: assembled by `app/ai_context.py` from already-computed values only (latest price/SMA/RSI/zone/trend, System 1 signal, Value Buy signal, both systems' backtest summaries) — never raw price data, never anything the AI itself computed. This is what makes "AI cannot fabricate a number" mechanically true, not just a stated intention.
  - System prompt enforces: ground answers only in the provided context, never fabricate a number, explicitly decline direct buy/sell/hold advice (verified working across multiple phrasings), say plainly when something is out of scope, and reply in **plain prose with no markdown** (the chat UI renders plain text, so markdown syntax like `**bold**` would leak through as literal asterisks — a real bug caught and fixed during Phase 9 review).
  - Conversation is multi-turn but **stateless server-side** — the browser resends the full growing history with each request; nothing is persisted to a database (none exists yet; that's Phase 10).
  - One chat box per stock page (not a separate global assistant page), auto-scoped to that stock's context.
- Hosting: **Render free tier** (free, connects to GitHub, auto-deploys on push). Trade-off already accepted: sleeps after 15 min idle, ~40s wake time for the first visitor after a quiet period — fine for the ~10 users (self, family, friends) this is built for.
- Indicators. **Moving averages are SIMPLE (SMA), project-wide, unless a specific system's notes say otherwise** — corrected by the user 2026-07-31 at the start of Phase 5, and confirmed to apply beyond System 1 (Systems 2/3 default to SMA too, but still confirm per-system when those phases start, in case that system's notes specify something different). This **supersedes** an earlier Phase 3 answer of "EMA": when asked SMA-vs-EMA in the abstract the user said EMA, then on reading the actual System 1 rules out of the notes corrected it to SMA. System 1's specific MA is a **20-period SMA computed over the last 20 weekly candles** (not 20 daily candles) — confirmed via a numeric comparison on real Maruti data. RSI uses **Wilder's original smoothing** (matches TradingView/investing.com defaults). Swing highs/lows use an **N-bar fractal** definition (a candle's high/low must exceed its `n` neighbors on each side), `n=2` by default — easy to retune later, not a locked decision like the RSI method.

**Design direction: "The Ledger."** Chosen 2026-07-30 over two rejected alternatives ("Instrument" — dark/kinetic terminal look; "Daylight" — bright/editorial look). Concept: a printed financial record annotated by hand in the margin — deliberately echoes the user's own handwritten notebook that the trading systems came from. Implemented Phase 4 (2026-07-31) in `app/static/style.css`.
- Palette (final hex, locked in Phase 4): paper `#f5f1e6`, ink `#1a1a1a`, brass `#a6763d`, forest green (up) `#1e5631`, oxblood (down) `#4a0e0e`, hairline rule `rgba(26,26,26,0.18)`. No drop shadows, no floating cards — hairline rules only, because paper doesn't have shadows.
- Typography: **IBM Plex** family throughout, self-hosted as woff2 files in `app/static/fonts/` (no Google Fonts CDN dependency) — Plex Serif for prose, Plex Mono for tabular numeric figures (`.figure` CSS class, `font-variant-numeric: tabular-nums`), Plex Sans for margin annotations. Chosen because all three are designed together as one family (guaranteed visual harmony) and are open-source/self-hostable.
- **Computed vs AI distinction = printed ink vs margin note.** Computed values live in the main column, in ink. All AI/system-written interpretation lives in a dedicated right-hand margin (`.margin-note` class), different (humanist) typeface, brass color, indented — visually unmistakable as "someone annotating," no label needed. On mobile (`.ledger-layout` grid collapses under 720px), the margin reflows to sit directly beneath the number it annotates, keeping the brass color/indent. Verified visually via screenshot in both desktop and 375px mobile viewports.
- No dark mode planned (The Ledger *is* paper — a dark version would be a different design entirely).
- **Chart colors — colorblind validation done Phase 4 (2026-07-31):** simulated protanopia/deuteranopia/tritanopia (Machado et al. 2009 matrices) on forest green vs oxblood. Deuteranopia (most common) reduces their RGB distance from 91.4 to 60.4 — both read as similar dark olive/brown, a real risk. Mitigation: candles use a redundant non-color cue, not a palette change — **filled body for up, hollow/outline-only body for down** (standard charting convention). Applies to all future chart/signal UI, not just Phase 4's chart.
- Chart library: **TradingView Lightweight Charts v4.2.3**, vendored locally in `app/static/vendor/lightweight-charts.js` (not CDN) — same self-reliance pattern as the fonts and the Phase 1 price data.

**Scope.** No deadline. No formal grading rubric except "must show AI integration" for a presentation. ~16 hours/week available. Single user today, but designed for the user + family/friends (~10 people max) from day one — hence live internet hosting and a database that has a concept of "user" even before login screens exist. ₹0 budget for everything (hosting, AI).

## Phase plan and current status

Full 14-phase breakdown (0 through 13) with hour estimates was presented and approved by the user. Summary:

| # | Phase | Status |
|---|---|---|
| 0 | Foundation (repo, env, minimal app, start script) | **Done** — see below |
| 1 | Data pipeline (15yr daily prices, 5 stocks, split-adjusted) | **Done** — see below |
| 2 | First deployment (live URL) | **Done** — see below |
| 3 | Indicator engine (RSI, MAs, candles, swings) | **Done** — see below |
| 4 | Charts + The Ledger visual identity | **Done** — see below |
| 5 | System 1 — Trend Following | **Done** — see below |
| 6 | Backtest engine | **Done** — see below |
| 7 | Explanation engine (the margin notes) | **Done** — see below |
| 8 | System 3 — Value Buy | **Done** — see below |
| 9 | AI conversational layer | **Done** — see below |
| 10 | Watchlist + journal | **Done** — see below |
| 11 | Screener | **Done** — see below |
| 12 | Polish (mobile, errors, disclaimers, performance) | **Done** — see below |
| 13 | System 2 — Cup pattern | **Done** — see below |

### Phase 0 — done (2026-07-31)

- Git initialized, `.gitignore` written, pushed to `github.com/gs2246/Investiq---ai` (private), branch `main`.
- `.venv` virtual environment working, Python 3.14.6.
- FastAPI + Uvicorn + Jinja2 installed, pinned in `requirements.txt`.
- Minimal app skeleton: `app/main.py` (FastAPI app, static file mount, one route), `app/templates/home.html`, `app/static/style.css` (placeholder only — real Ledger CSS arrives Phase 4).
- `start.bat` — double-click to activate venv and launch the dev server with auto-reload.
- Verified locally: home page and CSS both return HTTP 200.
- Two commits pushed.

### Phase 1 — done (2026-07-31)

- Added `yfinance` and `pandas` to `requirements.txt` (pinned to actual installed versions: `yfinance==1.5.2`, `pandas==3.0.5`).
- `scripts/download_data.py` — one-time download of daily OHLCV for the 5 seed stocks (`MARUTI.NS`, `RELIANCE.NS`, `INFY.NS`, `HDFCBANK.NS`, `BAJAJ-AUTO.NS`) from Yahoo Finance, 2011-01-03 to present (3,845 daily rows each). Saves an untouched copy to `data/raw/` and a cleaned copy (snake_case columns, ascending date order, prices rounded to 2 decimals) to `data/daily/`. Both adjusted and unadjusted close are kept; adjusted is what all future computation should use.
- `scripts/resample_data.py` — derives weekly (`data/weekly/`, calendar week ending Friday, 813 rows) and monthly (`data/monthly/`, calendar month end, 187 rows) candles from the daily CSVs only — Yahoo is never queried twice, daily is the single source of truth.
- `scripts/verify_data.py` — automated integrity checks (nulls, duplicate dates, date ordering, OHLC sanity, gaps, corporate-action ratio-shift detection) on every daily file. All 5 stocks passed with no issues; the only ratio shifts detected were routine annual/semi-annual dividend adjustments, not splits/bonuses.
- Manually cross-checked two data points against Google Finance (Maruti and Infosys previous-close) — both matched the pipeline's output exactly.
- Committed: "Add Phase 1 data pipeline: download, resample, and verify NSE price history".

### Phase 2 — done (2026-07-31)

- Added `render.yaml` (Blueprint config): Python web service, `pip install -r requirements.txt` build command, `uvicorn app.main:app --host 0.0.0.0 --port $PORT` start command, free plan.
- Pushed all local commits (Phase 0 + Phase 1 + render.yaml) to `github.com/gs2246/Investiq---ai`, branch `main`.
- User created a Render account, connected it via GitHub, and deployed the Blueprint. Render assigned the live URL (not fully user-chosen — it appended a random suffix): **https://investiq-ai-l6yf.onrender.com**
- Verified the live URL serves the real home page ("InvestIQ AI" title, "Algorithms calculate. AI explains." tagline) — confirmed via an independent fetch, not just Render's dashboard status.
- Cold start / 15-min-idle sleep trade-off already accepted (see "Decisions already made" above) — not re-litigated here.

### Phase 3 — done (2026-07-31)

- `app/indicators.py` — pure calculation library: `ema(series, period)`, `rsi(series, period=14)` (Wilder's smoothing), `swing_points(df, n=2)` (N-bar fractal). All seeded to match standard charting-platform behavior (SMA-seeded EMA, Wilder-seeded RSI average) rather than a naive recursive seed, so values match real charts even in the earlier years of the 15-year series.
- `scripts/verify_indicators.py` — cross-checks the production RSI/EMA against independent from-scratch reimplementations (plain Python, no pandas/numpy): exact match (0.00e+00 difference) across all 5 stocks. Also checks RSI stays within [0, 100] and hits its extremes on monotonic price moves, and verifies swing-point detection on synthetic data.
- No routes/charts/signals yet — this is a computation library only, to be consumed by Phase 4 (charts) and Phase 5 (System 1 signals).

### Phase 4 — done (2026-07-31)

- `app/static/style.css` — full Ledger design system (see "Design direction" above for final hex values, fonts, layout).
- `app/static/fonts/` — 6 self-hosted IBM Plex woff2 files (Serif/Sans/Mono × 400/600).
- `app/static/vendor/lightweight-charts.js` — vendored TradingView Lightweight Charts v4.2.3.
- `app/stocks.py` — new shared `TICKERS` dict (single source of truth for the 5 seed stocks); `scripts/download_data.py` now imports from it instead of duplicating the list.
- `app/main.py` — added `GET /stock/{symbol}` (chart page) and `GET /api/stocks/{symbol}/candles?timeframe=` (JSON: candles + EMA(20) + RSI(14), both restricted to the 5 known symbols). Candle open/high/low are scaled by the adj_close/close ratio so the chart shows split-adjusted shapes consistent with the indicators, not a raw-vs-adjusted mismatch.
- `app/static/js/chart.js` — renders candlesticks + EMA overlay + a synced RSI pane below. Up candles filled, down candles hollow-with-oxblood-border (the colorblind mitigation above).
- `app/templates/stock.html` (new), `app/templates/home.html` (updated to list all 5 stocks, was a dead end before).
- Verified with real Playwright screenshots (desktop + 375px mobile) and a console-error check — not just curl status codes. Zero failed requests, zero console errors. Playwright itself was a temporary verification tool, not added to `requirements.txt`.

### Phase 5 — done (2026-07-31)

- **Fixed a Phase 4 regression first:** Phase 4 had charted EMA(20) before the SMA correction landed. Added `sma()` to `app/indicators.py`, switched the `/api/stocks/{symbol}/candles` endpoint and `chart.js` from EMA to SMA, updated `verify_indicators.py`'s cross-checks accordingly. Re-verified visually so the chart shows the same line the signals actually trade on.
- `app/systems/trend_following.py` — the System 1 state machine (rules below), walked chronologically over weekly candles since BUY/SELL depend on whether a position is already open (inherently stateful, not vectorizable the way the Phase 3 indicators were).
- `scripts/verify_system1.py` — cross-checked against an independent from-scratch reimplementation (exact match, all 5 stocks), state-sequence invariants (no BUY-while-in-position, no SELL-while-flat), and a hand-built synthetic BUY→SELL scenario. Two real bugs surfaced during this process and both turned out to be in the *verification script*, not production code: pandas 3.x silently converts Python `None` to `NaN` in a string-typed DataFrame column (broke a naive equality comparison), and an early synthetic price fixture had net upward drift that pushed RSI past 60 before the SMA(20) window even opened, hiding the real crossover. Both documented in the script's comments.
- `GET /api/stocks/{symbol}/system1` endpoint (weekly-only; System 1 isn't defined on daily/monthly candles).
- Chart page: BUY/SELL arrow markers on the price chart (green up-arrow / oxblood down-arrow, only shown when viewing weekly - cleared on daily/monthly since the signals aren't defined there), plus a "current signal" block in ink/tabular figures with the Monday-check UI copy. Verified visually via Playwright screenshot, zoomed in enough to see individual BUY/SELL markers land exactly on the SMA crossing points.

## System 1 — Trend Following: the rules (from the user's notes, 2026-07-31)

Authoritative. Supplied by the user directly out of their handwritten notes — do not re-derive, re-interpret, or "improve" these without asking. All evaluation is on **completed weekly candles**, using the **20-period SMA** and **RSI(14)** (Wilder).

**Entry (BUY)** — only fires when flat:
- RSI(14) *crosses* from `<= 60` to `> 60`, i.e. `prev_rsi <= 60 AND rsi > 60`. Must be a crossover, **not** a level test.
- AND weekly close > 20-SMA.

**Exit (SELL)** — only fires when in a position:
- Weekly close < 20-SMA.
- This is simultaneously the exit *and* the trailing stop-loss — there is **no separate fixed stop**. RSI is irrelevant to the exit.

**State machine** — four states, one evaluated per completed weekly bar:

| State | Condition |
|---|---|
| `BUY` | flat, entry condition met |
| `HOLD` | in position, close >= 20-SMA |
| `SELL` | in position, close < 20-SMA |
| `NEUTRAL` | flat, no trigger |

- Within `NEUTRAL`, additionally flag **`DEVELOPING`** when close > 20-SMA AND RSI is between 50 and 60 AND rising. To be surfaced on the watchlist (Phase 10).
- Note the deliberate asymmetry: entry needs close **>** SMA (strict), `HOLD` needs close **>=** SMA. At exactly equal you keep an open position but cannot open a new one.

**UI copy note:** the system is designed to be checked on **Mondays**, once the prior week's candle has closed. Any "current signal" shown must make clear which week-ending date it refers to, and must never present an in-progress week as a completed signal.

### Phase 6 — done (2026-07-31)

- **All backtest money is hypothetical** — no real trades, no real capital anywhere in the app. Explicitly confirmed with the user at the start of this phase; the UI says so on every backtest view, not just here.
- Capital amount is a **user-customizable input**, not a fixed constant (the user pushed back on an initial "just pick a fixed number" framing — right call, since other people besides the user may use this tool). Compounds trade-to-trade per stock (the user's explicit choice over a reset-every-trade default); sits flat (no return) during weeks a stock isn't held. No transaction costs modeled yet (pure price-based returns — a deliberately deferred refinement, see Phase 5 Q&A). An open position at the end of the data is mark-to-market, shown separately from closed-trade stats.
- `app/systems/backtest.py` — `run()` (per-stock trade log + equity curve) and `run_portfolio()` (splits total capital equally across the 5 stocks, sums their independent equity curves; each stock's capital is never shared or reallocated between stocks).
- `scripts/verify_backtest.py` — cross-checked against an independent from-scratch reimplementation (exact match, all 5 stocks) plus invariants (equity always positive, win flag matches return sign, at most one open trade and only as the last entry, portfolio equity equals the sum of the 5 per-stock equities). One real bug surfaced and fixed: the same pandas `None`-vs-`NaN` gotcha from Phase 5 recurred in this verification script's naive reimplementation — documented inline this time.
- `GET /api/stocks/{symbol}/backtest?capital=` and `GET /api/portfolio/backtest?capital=` endpoints.
- UI: trade log table + equity curve chart added to each stock page (capital input, recalculates on change), plus a new `/portfolio` page for the combined view. Trade returns color-coded green/oxblood, reusing the same up/down convention as the candlestick chart. Verified visually via Playwright screenshots of both pages, zoomed into the trade table to confirm the color-coding actually rendered.
- Real result worth remembering: System 1 backtests **negative on Reliance** (-14.20%) over 2011–2026 despite being profitable on the other 4 stocks — the engine reports history accurately, including the parts that don't flatter the strategy.

### Phase 7 — done (2026-08-01)

- `app/rsi_zones.py` — `zone()` (page 1's 3-band instantaneous reading) and `trend()` (page 12's 5-state behavioral reading). The page-12 overlap ambiguity (see item 1 below) was resolved this phase with a constructed rule, not verbatim from the notes: "strong" zones (60–80, 20–40, extended past 80/below 20) apply by RSI value alone; the overlapping 40–60 middle is broken by RSI's direction vs. **1 week ago** (matching System 1's own 1-week lookback) — rising → Uptrend, falling → Downtrend, roughly flat (±0.5 points) → Sideways. Flagged as an assumption in the module's own docstring, not a notes-verbatim rule, so it's easy to correct later.
- `app/explanations.py` — deterministic, template-based 1–2 sentence text for RSI zone, RSI trend, the System 1 signal, and backtest results. Still fully rule-based (no AI, no network calls) — this is *not* the LLM layer, that's still Phase 9.
- Wired into `/api/stocks/{symbol}/system1` (adds `rsi_zone`/`rsi_trend` per row plus a `notes` object) and both backtest endpoints (adds a `note` field).
- **Stock page restructured**: the single static margin-note placeholder from Phase 4 is gone. Each computed section (System 1 signal, RSI zone/trend, backtest summary) now has its own adjacent margin note — this is what the Phase 4 design was always meant to do, just unbuilt until this phase. `.ledger-layout` (the two-column ink/margin grid) is now used multiple times per page, once per annotated section, rather than once for the whole page. Verified the mobile reflow still works per-section (each note now sits directly under its own section, not bundled at the page bottom).
- `scripts/verify_explanations.py` — a different kind of check than earlier phases (no formula to get wrong, so no numeric cross-check): exhaustiveness (every classification label the code can produce has a matching explanation) plus a printout of all 5 stocks' actual generated language for manual read-through, since accuracy of *wording* isn't something an automated check alone can confirm.
- One thing that looked like a bug but wasn't: explanation text containing em-dashes displayed as mangled `â€"`-style garbage through `curl | python` in the terminal. Confirmed via raw byte inspection that the actual UTF-8 bytes (and the browser rendering) were correct throughout — the corruption was a Windows Git Bash stdin-piping artifact in the diagnostic command, not a real encoding bug anywhere in the app.

### Phase 8 — done (2026-08-01)

- `app/systems/value_buy.py` — the full mechanism: monthly RSI context (computed from the existing daily-derived `data/monthly/`), an as-of join to weekly bars via `pandas.merge_asof` (verified no-lookahead — a weekly bar only ever sees an already-closed month), and the arm/trigger/expire/re-arm/bracket-exit state machine. `evaluate()` is a thin wrapper; the actual weekly loop lives in `run_weekly_state_machine(ohlc, context, swing_lookback)`, deliberately split out so it can be tested against a hand-crafted context series without needing to craft real price data that produces an exact RSI pattern (a lesson from Phase 5's verification).
- **Real bug found and fixed during verification**: the swing-high target could land at or below the entry price when the lookback window was thin (early data, or a smaller `swing_lookback`), producing a nonsensical trade. Never occurs in the actual 5-stock/20-week-lookback dataset, but a genuine latent bug since the lookback is a configurable parameter — now such an entry is skipped (setup stays armed) rather than firing.
- `app/systems/backtest.py` refactored to extract `compound_equity_curve()` and `summarize()` as shared helpers, so System 1 and System 3 use identical capital-compounding rules. Re-ran Phase 6's `verify_backtest.py` after the refactor — zero regression, byte-identical numbers to before.
- `scripts/verify_value_buy.py` — cross-checked against an independent reimplementation (exact match, all 5 stocks) plus 6 targeted synthetic scenarios (happy path, 2-week expiry, re-arming, stop-loss exit, one-position-at-a-time, context-required). Two of the early scenario failures were bugs in the *test fixtures themselves* (a rounding mismatch in the comparison, and a synthetic candle that was accidentally green instead of red) — documented inline once found, same pattern as earlier phases.
- `GET /api/stocks/{symbol}/value-buy?capital=` endpoint (signal + trade log + equity curve combined, since Value Buy's "signal" is inherently trade-level).
- `app/explanations.py` extended with Value Buy's own margin-note templates (NEUTRAL/ARMED/BUY/HOLD/SELL-stop/SELL-target).
- **UI**: a new, visually distinct "Value Buy — technical pullback entry" section on the stock page, separate from System 1's per the user's explicit instruction, with the "not fundamental value investing" clarification shown directly and boldly in the UI copy (not buried in a margin note) — the user was explicit that beginners would otherwise assume fundamentals. Trade table includes stop/target/risk-reward/exit-reason columns System 1's doesn't need. Verified visually (desktop + mobile reflow) via Playwright screenshot.
- Real result worth remembering: Bajaj Auto has **zero** Value Buy trades across the full 15-year history — its monthly RSI touched the 38–45 zone only twice, and both times *falling* into it rather than rising, so correctly never qualified as context. Infosys is currently **ARMED** at ₹1187.70 (live, as of 2026-07-31).

### Phase 9 — done (2026-08-01)

- **`.env`** created with the user's real Gemini API key (obtained free at aistudio.google.com, walked through step by step); `.env.example` committed as a template with no real secret. Confirmed `.env` itself never appears in `git status` — correctly gitignored.
- `app/ai_provider.py` — the swappable provider interface (`GeminiProvider.chat(messages, system_prompt)`), plus `get_provider()` which returns `None` when no key is configured. `AIUnavailableError` is the single exception type callers must handle, covering both "no key" and real provider failures (network, invalid key, empty/blocked response).
  - Model name had to be fixed mid-phase: the first choice (`gemini-2.5-flash`, a dated snapshot) returned `404 ... no longer available to new users` on a real API call despite appearing in the list-models response. Switched to `gemini-flash-latest`, a generic alias — see "Decisions already made" above.
- `app/ai_context.py` — `build_context()` assembles a plain-text snapshot of a stock's already-computed state (price/SMA/RSI+zone+trend, System 1 signal, Value Buy signal, both systems' backtests) for the system prompt; `build_system_prompt()` wraps it with the guardrail instructions (ground answers only in the given data, never fabricate, decline direct buy/sell/hold advice, plain prose no markdown).
- `POST /api/stocks/{symbol}/ask` endpoint. Stateless server-side — client resends the full conversation history each call. Returns `{"reply": ..., "error": null}` on success or `{"reply": null, "error": "..."}` on any failure (missing key or provider error) rather than raising an HTTP error, so the frontend always gets a clean, renderable response.
- UI: a chat box at the bottom of each stock page (`app/static/js/ai_chat.js`), reusing the established ink-vs-brass visual language — the user's own questions rendered in ink/serif labeled "You", the AI's replies in brass/humanist-sans labeled "AI", hairline rules between turns. History kept in a browser-only JS array, nothing persisted (no database yet — that's Phase 10).
- Verified with real API calls, not mocks: grounded accuracy (every number the AI cited matched computed values exactly, nothing fabricated), the buy/sell/hold guardrail held across multiple phrasings, multi-turn follow-ups correctly used prior context, and — the core Phase 9 requirement — every other endpoint (`candles`, `system1`, `backtest`, `value-buy`) kept returning 200 with `.env` temporarily removed, while the chat alone showed a clear "AI is not configured on this server" message. Confirmed via direct DOM inspection (not just a screenshot) that the error text and re-enabled input both render correctly.
- One real bug found and fixed during review: the AI's replies used markdown (`**bold**`, `*` bullets), which rendered as literal asterisks in the plain-text chat UI. Fixed via a system-prompt instruction ("reply in plain prose, no markdown") rather than adding a markdown parser — simpler and sufficient.
- **Security note:** the user's real API key was pasted directly into this chat conversation to hand it off. Flagged to the user in the moment (chat logs may persist; regenerate the key at aistudio.google.com anytime if concerned) rather than silently proceeding.

### Phase 10 — done (2026-08-01)

- **Database provider chosen after research, not assumption:** confirmed Render's own free Postgres deletes the database after 30 days unless upgraded — ruled it out despite already hosting there. Picked **Neon** over Supabase (see "Decisions already made" above for the full reasoning).
- `.env` gained `DATABASE_URL` (user walked through Neon signup step by step, same gitignored pattern as the Gemini key); `.env.example` updated to document it.
- `app/models.py` — `WatchlistItem` and `JournalEntry` SQLModel tables, both with a real `user_id` column defaulting to a single shared `DEFAULT_USER_ID` (no login screen exists yet).
- `app/db.py` — engine setup, `is_configured()`/`init_db()` mirroring `app/ai_provider.py`'s graceful-degradation pattern from Phase 9. Tables created automatically on startup via FastAPI's lifespan handler.
- API endpoints: `GET/POST /api/watchlist`, `DELETE /api/watchlist/{symbol}` (watchlist rows include each stock's *current* System 1 and Value Buy signal, reusing existing computation — no new signal logic); `GET/POST /api/journal`, `DELETE /api/journal/{id}` (journal entries are **real trades the user actually made**, distinct from the hypothetical backtest trades shown elsewhere).
- UI: new `/watchlist` page (add/remove stocks, DEVELOPING/ARMED states bolded per the Phase 5 rule that flagged this as watchlist-relevant) and `/journal` page (a form + trade table, BUY/SELL color-coded green/oxblood matching the existing convention). A watchlist toggle button was also added directly to each stock page for convenience.
- **Two real bugs found during verification, both fixed:**
  1. The browser's default HTTP cache could serve a stale GET response for `/api/watchlist`/`/api/journal` after a write, showing outdated state. Fixed by adding `cache: "no-store"` to those fetches.
  2. Free-tier Neon's per-request latency (1-3+ seconds, serverless cold connections) made every write-then-refresh button look unresponsive/broken with no feedback. Fixed by adding explicit "Updating…/Adding…/Removing…/Deleting…" states — now the standard pattern for any future database-backed UI, not just this phase's.
- Verified with real operations against the live database (not mocks): full CRUD round-trip, duplicate-add protection, input validation, data survives a full app process restart (the exact failure mode that ruled out Render's own free tier), and every non-database part of the app stays fully functional (200 OK) with the database disconnected — only the two new features show a clean 503.
- All test data created during verification was deleted from the real database before finishing - what's live now is what the user's own testing produces, not leftover fixtures.

### Phase 11 — done (2026-08-01)

- `GET /api/screener` — returns all 5 stocks' current computed state in one call: latest weekly close price, RSI zone, RSI trend, System 1 state (+ developing flag), Value Buy state. All values reuse existing computation, nothing new is calculated — `app/main.py`'s `_screener_row()` is a superset of the old `_current_signals()` helper (which the watchlist endpoint uses); `_current_signals()` now delegates to it rather than duplicating the Value Buy evaluation call.
- `/screener` page (`app/templates/screener.html`, `app/static/js/screener.js`) — one table, one row per stock, all 5 shown at once (fetched in a single request, no pagination needed at this scale). A dropdown filter above each of the four state columns (RSI Zone, RSI Trend, System 1, Value Buy) narrows the visible rows client-side; System 1's filter includes a synthetic `DEVELOPING` option (matches `state === "NEUTRAL" && developing`, since developing is a flag on NEUTRAL rather than its own state). DEVELOPING/ARMED bolded using the same `.watchlist-noteworthy` convention as the watchlist page.
- Added a small `.filter-row` CSS alias sharing rules with the existing `.journal-form-row` flex layout (same label+select row pattern, no new visual language introduced).
- Nav link (`Screener`) added to every page's header tagline (home, watchlist, journal, portfolio, stock).
- Verified visually via Playwright (installed temporarily, uninstalled after — same pattern as Phase 4/10): unfiltered table (all 5 stocks, Maruti shown DEVELOPING, Infosys shown ARMED — matches the live state noted in Phase 8), a filter narrowing to just the one ARMED stock, the empty-state row when a filter combination matches nothing, and the mobile (375px) reflow. Zero console errors across all four checks.

### Phase 12 — done (2026-08-02)

Scoped with the user up front into 4 concrete areas rather than left vague: disclaimers get a site-wide footer (not just per-feature), errors get a full audit of every page/endpoint (not just the highest-risk flows).

- **Disclaimers:** a persistent footer ("InvestIQ AI is an educational project, not financial advice...") added to every page (home, stock, portfolio, watchlist, journal, screener, and the new error page) via `.site-footer` + the existing `.ui-hint`/`.hairline` classes — no new visual language.
- **Errors — backend:** added an `HTTPException` handler in `app/main.py` that branches on path: `/api/*` routes keep returning plain JSON (unchanged, existing frontend error handling depends on `data.detail`), but HTML page routes (e.g. an unknown `/stock/{symbol}`) now render a styled `error.html` page instead of a raw JSON blob — a person, not a script, is the one who'll actually see a mistyped URL. Journal/watchlist backend input validation was already solid from Phase 10 (positive quantity/price, known symbol, BUY/SELL enum) — audited, no gaps found.
- **Errors — frontend:** every page's JS previously assumed the network would succeed. If a `fetch` itself threw (server unreachable, not just a non-200 response), pages were left stuck on "Loading…" or a button stuck disabled on "Adding…/Removing…" forever, with no feedback. Added `try/catch` around every fetch call across `chart.js`, `backtest.js`, `value_buy.js`, `portfolio.js`, `watchlist.js`, `journal.js`, `watchlist_toggle.js`, and `screener.js` (`ai_chat.js` already handled this correctly from Phase 9 - used as the reference pattern). A shared `#page-error` element added to `stock.html` for its chart/system1 load failures; other pages reuse their existing error/summary text elements. Capital inputs (backtest, Value Buy, portfolio) now show an explicit message for non-positive values instead of silently doing nothing.
- **Mobile (375px), a real bug found and fixed:** systematically checked every page's `document.documentElement.scrollWidth` vs viewport width, not just eyeballing screenshots. Found genuine horizontal-scroll bugs: (1) trade tables (up to 10 columns on the Value Buy table) don't shrink below their content width, forcing the whole page wider — fixed with a `.table-scroll` (`overflow-x: auto`) wrapper div around every `<table class="trade-table">`, so only the table scrolls, not the page. (2) The portfolio page nested its entire content (including the TradingView equity chart) inside the `.ledger-layout` CSS grid; a `<canvas>`-based chart's intrinsic width doesn't respect a grid item's `min-width: auto` sizing, which pushed the grid track (and the whole page) wider than the viewport. Fixed by restructuring `portfolio.html` to match `stock.html`'s established pattern: only the text summary + margin note live inside `.ledger-layout`; the chart and table sit outside it, full-width, in normal block flow. Re-verified zero horizontal overflow on all 6 pages after the fix.
- **Performance:** `app/main.py` previously called `pd.read_csv()` fresh on every single API request, even though the price CSVs are static (downloaded once in Phase 1, never change at runtime). Added `_load_csv(timeframe, symbol)` with `@lru_cache` — safe because every caller only reads columns off the returned DataFrame, never mutates it (checked `value_buy.py` and `trend_following.py` specifically for in-place mutation before caching; both only build new DataFrames from columns). Removed 6 duplicate `pd.read_csv` call sites in favor of the cached loader.
- Verified with Playwright (installed temporarily, uninstalled after): all 6 pages + the new error page, at both desktop and 375px mobile, checked for the disclaimer footer's presence, zero console errors (the one console message logged was the *expected* 404 from the deliberately-broken test URL), and zero horizontal scroll at mobile width via direct DOM measurement (not just visual inspection, which is what caught the portfolio bug in the first place — it wasn't obvious from screenshots alone).

## System 3 — Value Buy: the rules (from the user's notes, 2026-08-01)

Authoritative. Supplied by the user directly out of their handwritten notes — do not re-derive, re-interpret, or "improve" without asking (same standing as System 1's rules above). **UI label: "Value Buy — technical pullback entry."** Explicitly **not** fundamental value investing (no P/E, no book value) — must say so visibly in the UI itself, not just a margin note, since beginners will otherwise assume fundamentals. Keep clearly separate from System 1 in both code and UI: System 1 buys strength (RSI > 60) with a trailing stop and no target; System 3 buys weakness (RSI ~40, rising) with a fixed stop and a defined target.

**Data dependency:** needs monthly RSI(14). **Confirmed 2026-08-01: computed from the existing `data/monthly/` (Phase 1, derived from daily candles)**, not re-derived from weekly as the notes' literal wording suggested — daily-derived month boundaries are more accurate (a week can straddle a month boundary; a day never does), and this avoids a second parallel "monthly" dataset. This overrides a literal instruction in the notes; flagged here in case it's ever revisited.

**Timeframe roles:** Monthly = context filter (gates everything). Weekly = trigger and execution.

**Entry (BUY)** — three stages, in order, only when flat (one position at a time per stock, confirmed 2026-08-01 — mirrors System 1):

1. **Context** (monthly): monthly RSI(14) between 38 and 45 **and rising** vs. the prior month (`rsi_monthly[m] > rsi_monthly[m-1]`). Falling into this range from above does **not** count as support — must be rising.
2. **Trigger** (weekly): a weekly candle closes green (`close > open`) while context is active. This is the "signal candle."
3. **Execution** (weekly): arm a stop-buy at the signal candle's **high**. Entry triggers only when a *later* weekly candle's high trades above that level; entry price = the signal candle's high (not the triggering week's own high). **This is a pending stop order, not a market-at-close entry** — must be modeled as such in the backtest or results are inflated.
   - Setup expires after 2 weeks if untriggered.
   - **Confirmed 2026-08-01:** if a new signal candle forms while a setup is already armed, it re-arms the setup at the new high and resets the 2-week expiry (rather than ignoring new signals until the pending one resolves).

**Exit** (either condition, whichever hits first — read as a bracket order since both are listed under "Exit"):
- **Stop loss:** signal candle's **low**. Fixed at entry, does **not** trail (unlike System 1's trailing SMA stop).
- **Target:** nearest swing high = **the highest-value** swing point (high exceeds both immediate neighbors) within the prior 20 weekly bars (lookback is a parameter). **Confirmed 2026-08-01: highest-value, not most-recent-in-time.**
- All-time high is displayed as secondary context only — risk-reward is computed against the swing-high target, not the ATH.

**Risk-reward**, computed and shown at entry (a fixed snapshot, not recalculated while held — both stop and target are fixed):
- `risk = entry - stop`
- `reward = target - entry`
- `ratio = reward / risk`

## Notes ambiguities — resolved for System 1 (2026-07-31)

Two ambiguities found in the user's handwritten trading notes (photographed and reviewed early in the project), surfaced again and explicitly confirmed before starting Phase 5:

1. **RSI band definitions.** Page 1 of the notes: 0–40 bearish / 40–60 sideways / 60–100 bullish (a clean, non-overlapping instantaneous reading). Page 12: an overlapping behavioral table (uptrend 40–80, strong uptrend 60–80, downtrend 20–60, strong downtrend 20–40, sideways 40–60) plus notes about RSI "taking support" or "resistance" at 60. **Confirmed:** these are two separate computed values, not a contradiction to resolve into one — page 1 is the instantaneous label, page 12 is the directional/behavioral state (did RSI bounce off 60, or fail to break above it). Both should be computed and exposed wherever RSI is shown. **Page 12's precise mechanics resolved in Phase 7** — see above.
2. **"20 DMA" on weekly charts.** Notes literally say "Day Moving Average" but every System 1 chart is weekly, and rules reference "20DMA of that week." **Confirmed: a 20-period SIMPLE moving average computed over the last 20 WEEKLY candles** (not 20 daily candles, and not exponential) — "D" was leftover habit from daily-chart terminology; page 11's investing.com setup instructions ("Format MA → Input → 20" on a weekly chart) apply a 20-*period* MA to whatever candle size is on screen. Confirmed with an explicit numeric comparison on real Maruti data (2026-07-31): 20-SMA-of-weekly = 13,373.05 vs 20-SMA-of-daily = 13,814.15 — user picked weekly. This was the single most consequential number in System 1 and is now locked in.

## System 2 — Cup & Handle: the rules (from the user's notes, 2026-08-02)

Authoritative. Supplied by the user directly out of their handwritten notes — do not re-derive, re-interpret, or "improve" these without asking (same standing as Systems 1 and 3's rules above). Resolves the "deferred, separate open item" that blocked Phase 13 in earlier sessions — the page-5/6/7 selling-ladder ambiguity and the entry/stop percentages are no longer open questions.

**Chart:** monthly candles. Universe: all caps. Minimum 5-year cup.

**Cup geometry** (all thresholds tunable parameters, not hard-coded — see `app/systems/cup_pattern.py`):
- Left rim: local high (highest in a ±3 month window)
- Cup bottom: lowest low after the left rim
- Right rim: a later local high recovering within 8% of the left rim
- Duration: left rim → right rim ≥ 60 months
- Depth: bottom is 12–50% below the left rim
- Rim symmetry: right rim within 8% of left rim price
- Rounded bottom: the lowest quartile of the cup's price range must account for ≥20% of the cup's duration (time spent near the bottom, not a V spike)

**Handle** (after the right rim) — **required** for a tradeable setup; "cup AND handle" is a joint pattern by name, so a cup with no qualifying handle is not treated as complete (detection keeps looking at later right-rim candidates instead — a deliberate refinement made during Phase 13's build, flagged to the user):
- Duration: 1–6 months
- Depth: retraces less than ⅓ of cup depth
- Position: sits in the upper third of cup height (implied by the same ⅓-retrace ratio, no separate check needed)

**Entry / stop** (relative to the BUY POINT = the handle's own high, which the notes call the "resolution point"):
- Entry: buy point × 1.04 (+4% breakout confirmation), as a **pending stop order** — triggers only when a later month's high crosses this level; entry price is the trigger level itself, same pending-order mechanic as System 3's Value Buy. No stated expiry, unlike Value Buy's 2-week arm window.
- Stop loss: buy point × 0.76 (-24%, the neckline level), fixed at entry.

**Selling ladder** — three independent, user-selectable modes sharing the same entry/stop (confirmed 2026-08-02: these are three deliberate trading modes, not revisions of each other):
- **Income:** sell ⅓ at +10%, sell ⅓ at +20%, hold the final ⅓. The original entry stop stays in force for the whole position for as long as any of it is held (confirmed — never raised, unlike Wealth/Trail).
- **Wealth:** sell ⅓ at +20% and another ⅓ at +40% (2 sells, holding a final ⅓ indefinitely); stop trails upward at every +10% gain milestone to (milestone − 10%), except the very first milestone (+10%) which raises the stop to +10% itself, not breakeven. E.g. +10%→stop +10%, +30%→stop +20%, +40%→stop +30% (+ sell), …, +110%→stop +100%. Confirmed the pattern repeats indefinitely past +60%.
- **Trail:** the identical stop ladder as Wealth, but no partial sells — the whole position rides until the trailing stop is eventually hit.

**Honesty requirement, stated explicitly by the user and treated as a hard design constraint:** geometric cup detection is fuzzy and 5-year cups are rare. The UI must present detector output as "POSSIBLE cup formation — review the chart," never as a definitive BUY signal the way Systems 1 and 3 do. The entry/stop/ladder math is deterministic and only shown once a human has confirmed the buy point.

### Phase 13 — done (2026-08-02)

- **Real-data tuning session before any code was written**, per the user's explicit request ("show me your detection approach on real Maruti monthly data so we can tune thresholds"). A prototype detector (temporary, scratchpad-only) found **zero geometrically valid cups across all 5 stocks over 15 years** at the notes' exact thresholds. Depth (12–50%) and duration (≥60 months) were frequently satisfied; **rim symmetry (±8%) was almost never satisfied** — every candidate right rim overshot the left rim by 35–450%, never landed close. Shown to the user with a diagnostic chart (Maruti monthly close + detected local highs, generated via a temporarily-installed matplotlib, uninstalled after). **Confirmed with the user: keep ±8% as a strict band as written** — the honest, expected outcome on these particular strong long-term compounders, not a bug to chase. This finding is re-verified in `scripts/verify_cup_pattern.py`'s real-data cross-check every time it runs.
- Two more mechanical ambiguities resolved with the user before writing the exit-ladder code (both now recorded above): whether Income's final ⅓ keeps the original stop (yes), and whether the Wealth/Trail ladder's "+10% raises stop to +10%, then milestone−10% after that" pattern repeats indefinitely past +60% with Trail using the identical schedule minus the partial sells (yes to both).
- `app/systems/cup_pattern.py` — `detect_cups()` (geometry + handle), `_find_entry()` (pending stop order, same mechanic as Value Buy), `_simulate_income/_wealth/_trail()` (the three ladder modes), `run_backtest()` (one position at a time per stock, same discipline as Systems 1/3), `current_status()` (for the live signal panel — the most recently formed complete setup, not backtest sequencing). A genuine bug caught during implementation, not just verification: `detect_cups()` naturally returns cups ordered by left-rim date, but two overlapping cups can resolve their *entries* out of that order — `run_backtest()` now explicitly sorts by entry index before walking chronologically, since `app.systems.backtest.compound_equity_curve` requires trades in chronological order to match them up correctly.
- Backtest trades from a single cup can involve up to 3 partial-sell tranches (Income/Wealth) — collapsed into one blended entry/exit trade (a weighted-average return, `_blend_trade()`) so the existing shared `compound_equity_curve`/`summarize` helpers (built for one entry → one exit) keep working unmodified across all 4 systems. The per-tranche detail (dates, fractions, exit reasons) is preserved in a `tranches` field for the UI, even though the equity curve itself only reflects the blended outcome — a deliberate, documented simplification of intra-trade cash-flow timing, acceptable given how rare a complete setup is expected to be.
- `scripts/verify_cup_pattern.py` — real-data cross-check (independent rim-detection reimplementation + the zero-cups finding above, all 5 stocks) plus a hand-built ~76-month synthetic series exercising the full pipeline (a right-rim candidate that fails to grow a handle and must be rejected, a second candidate that succeeds, and confirms the pending-stop entry price is the trigger level, not the triggering month's actual high) plus isolated scenario tests for all three ladder modes. One real off-by-one bug caught *while writing the verification fixtures themselves*, not the production code: `_simulate_wealth`/`_simulate_trail` start processing at `entry_idx + 1`, so a fixture without a leading dummy "entry bar" row silently shifted every intended milestone by one position — documented inline once found, same pattern as every previous phase's verification bugs.
- **New DB table** `CupConfirmation` (`app/models.py`) — a human's confirmation that a detected "POSSIBLE cup" is real, keyed by `(user_id, symbol, left_rim_date)` so the same cup can't be double-confirmed (enforced by a real unique constraint, verified against the live Neon database: insert, query, duplicate-rejection, delete). Session-only was the other option discussed with the user; persisted was chosen so a confirmation survives a page refresh.
- `GET /api/stocks/{symbol}/cup-pattern` (state + geometry + confirmation status + a backtest per ladder mode) and `POST /api/stocks/{symbol}/cup-pattern/confirm` (recomputes the current cup server-side rather than trusting client-supplied numbers — the client sends no body at all).
- **UI**: a new "Cup & Handle — long-term base pattern" section on the stock page, visually and behaviorally distinct from Systems 1/3 per the honesty requirement — never an automatic BUY badge, always "POSSIBLE cup formation — review the chart" until confirmed, and a "Confirm this cup" button that only appears when there's something to confirm. A selling-ladder mode dropdown (Income/Wealth/Trail) switches which backtest (summary/note/equity chart/trade table) is displayed, rather than showing all 3 simultaneously.
- **Verified against real production thresholds** (all 5 stocks, both desktop and 375px mobile, via Playwright): every stock correctly shows "No possible cup formation detected," no confirm button, flat equity curve, zero horizontal overflow. **Also verified the full confirm/backtest/mode-switching flow visually**, which real data can't reach at the strict thresholds — done by temporarily monkey-patching `cup_pattern.RIM_SYMMETRY`/`BOTTOM_DWELL_FRAC`/depth bounds in a throwaway second server process (never touching the actual module file), confirming a real cup, watching the entry/stop/buy-point detail and mode-specific backtests render correctly, then deleting the test confirmation row from the live database afterward. One transient `psycopg2.OperationalError: SSL connection has been closed unexpectedly` surfaced on `/api/watchlist` during this pass and did not reproduce on retry — a known Neon free-tier characteristic already documented in Phase 10, not a Phase 13 regression (and already handled gracefully by Phase 12's frontend error handling, which just hides the affected button rather than crashing).

## Post-launch polish (2026-08-05)

All 14 phases were complete and deployed before this work. This round was **robustness and first-impression polish only** — explicitly scoped by the user as: no new features, and no changes to trading-system logic, signal math, backtest calculations, AI guardrails, or disclaimers. Five items, each investigated against the **live deployed app** before any code changed (the user's explicit instruction: "confirm what's real before fixing"), each committed separately.

1. **Load performance.** Measured the live site: `stock.html` loaded 7 **blocking** `<script>` tags serially, the first being the ~160KB vendored chart library, so nothing else (including the other scripts' `fetch()` calls) started until it finished. Static assets also had **no `Cache-Control` header at all** — the chart library was re-downloaded in full on every stock-page navigation within a session. Fixed both: `defer` on every script site-wide (parallel download, execution order preserved — verified `chart.js`'s global `symbol` still resolves for dependent scripts), and a `Cache-Control: no-cache` middleware scoped to `/static/` only. Deliberately `no-cache` (revalidate, cheap 304) rather than a real `max-age`, since a future deploy could otherwise serve a stale cached file.
   - **The ~30-60s Render cold boot itself is deliberately NOT fixed — decided 2026-08-05, do not re-raise.** Three options were presented with trade-offs (keep-alive ping, which burns free-tier compute-hours continuously and reverses the accepted scale-to-zero trade-off; server-side rendering the first view, a real architectural change touching every route + template; or a static splash shell on a second free host, the only option that can show anything during the wait). **The user declined all three** — the cold-start wait stays as the accepted free-tier trade-off it has been since Phase 2. For reference if this is ever revisited: local app import alone (pandas, SQLModel, Gemini client, DB engine) measures **3.3s**, so the app-boot share has grown since Phase 2's original ~40s measurement, though Render's container spin-up is still almost certainly dominant.
   - **Key constraint to re-state if this ever comes up again:** a cover page served *by the app* cannot appear during a cold start. The service is spun down, no process is running, and Render simply holds the browser's connection open until boot finishes — so there is nothing to serve. Only a separate always-on host can put anything on screen during that window. The cover page built on 2026-08-05 (item 6 below) covers the interval *after* the app responds; it does not and cannot shorten the wait before that.
2. **Skeleton loading states.** Every bare "Loading…" replaced with shape-matched skeletons (`.skeleton`, `.skeleton-text`, `.skeleton-chart`, `.skeleton-row` in `style.css`; `skeleton_rows()` Jinja2 macro in the new `app/templates/_macros.html`). Text/table skeletons are server-rendered so they appear before any JS downloads, and clear for free when real content is assigned; chart skeletons need an explicit `hideSkeleton()` call in a `finally` block. **Real bug found during verification:** TradingView's canvas gets its own compositing layer that `z-index: 1` does not reliably paint under — needed `z-index: 100`, confirmed empirically with a red-debug-color test, not assumed from the spec. **Also found:** watchlist/journal/screener had *no* loading feedback at all (blank tables until fetch resolved) — same treatment applied.
3. **Empty-state messages for trade tables.** Verified against production that Bajaj Auto genuinely returns 0 Value Buy trades today, rendering a bare header-only table. `backtest.js` (System 1) and `value_buy.js` had no empty-state handling; `portfolio.js` had the same gap (fixed for consistency though unlikely to trigger). `cup_pattern.js` already had one from Phase 13 and was left alone. Messages are **system-specific** ("No Value Buy setups occurred in this stock's history."), since zero trades is often the correct, expected outcome — not a bug.
4. **First-visit orientation note** (`app/static/js/orientation.js`). A quiet hairline-ruled note on stock pages pointing new users to the Screener, dismissed permanently via `localStorage`. Rendered `hidden` in markup and revealed by JS so returning visitors never see it flash before removal; blocked/unavailable storage (private browsing) degrades to *showing* the note rather than throwing.
5. **Social/preview metadata.** Per-page Open Graph + Twitter `summary_large_image` tags via a `social_meta()` macro, plus `app/static/og-image.png` (1200×630) rendered through headless Chromium against the site's own stylesheet and self-hosted IBM Plex fonts, so the preview card is the real Ledger design rather than an approximation. **`og:image`/`og:url` are built from the incoming request, not hard-coded** — crawlers silently ignore relative image paths, and this keeps local/Render/any future domain correct with no config change. All existing per-page `<title>` tags confirmed intact. The error page deliberately gets **no** share preview, just `noindex`.

6. **Cover page while a page loads** (`app/static/js/splash.js`, `splash_cover()` macro, `.splash*` CSS). Added after the user saw the deployed site and said the loading state "does not look good" — they wanted an InvestIQ title page with "all the other background stuff" hidden until ready. **They chose the in-app cover over the static-host option**, having been told plainly it cannot cover the cold start itself. Applies to the 5 data-loading pages, deliberately **not** the home page (it renders complete server-side, so a cover there adds delay and hides nothing) and not the error page.
   - **Readiness is "nothing half-drawn is left": no fetch in flight AND no visible `.skeleton`.** Two earlier designs were caught failing by verification, not reasoning: (a) counting fetch promises alone uncovered the page while it was still visibly assembling, because a fetch settles at *headers* and `response.json()` downloads the body afterwards — fixed by holding each request open until `response.clone().arrayBuffer()` completes; (b) a 12s failsafe fired mid-load on a slow link, revealing the exact half-drawn page it existed to hide — measured full-draw times are ~1.1s unthrottled, ~3.8s at 2Mbps, ~21.2s at 300kbps, so the failsafe is now 25s (and the independent inline one 35s, which must stay the longer of the two).
   - Stall detection uncovers ~2.5s after the page stops changing when requests have settled but skeletons remain (i.e. loaders errored), so a total API failure lifts the cover in ~3.9s rather than making the visitor wait out the full 25s failsafe. Measured cover durations: 2.5s unthrottled, 5.0s at 2Mbps, 22.0s at 300kbps, 3.9s with every API failing.
   - Three independent escape hatches so it can never strand a visitor: `<noscript>` CSS, an inline timer that runs even if `splash.js` 404s, and `splash.js`'s own failsafe.
   - **Pre-existing bug found and fixed while testing this:** `watchlist_toggle.js`'s initial `refreshWatchlistToggle()` call had no `try/catch` (Phase 12 added one to the click handler but missed this one), so a network-level failure produced an unhandled promise rejection. Surfaced by the abort-every-request test.

**Deployed and verified live 2026-08-05:** all five items confirmed on the production URL (deferred scripts, `Cache-Control` on `/static/`, 30 server-rendered skeleton elements, the orientation note in markup, OG/Twitter tags with `og-image.png` returning HTTP 200). Notably `og:url`/`og:image` resolve to **`https://`**, not the internal `http://` — the real risk of deriving them from the request, since several crawlers reject mixed-content preview images.

**One outstanding check, deliberately deferred by the user:** whether the OG image actually *renders* in a real share card. The tags and image are confirmed live, but only a crawler can confirm the card itself — paste the URL into Facebook's Sharing Debugger or X's Card Validator when convenient. Not blocking anything.


## Beginner-usability round (2026-08-07)

Prompted by the user looking at the deployed site: the charts were "very cluttered because of the Buy and sell notes", and they wanted it cleaner, colour-coded, and understandable by a nervous beginner. They also raised robo-advisors ("robots which help investors decide where to invest") — see the boundary note at the end, which is the important part of this round.

1. **Chart decluttering.** Every one of a stock's 40-56 System 1 markers carried a "BUY"/"SELL" text label, across 794 weekly bars in ~900px. Measured per stock: Reliance 56, HDFC Bank 50, Bajaj Auto 47, Maruti 44, Infosys 40. At that density the labels collided into unreadable runs ("SESELLSELL", "BUYBUYBUY") and candles were about a pixel wide. Three fixes: markers keep their arrows but **drop the text** (direction + side of bar + colour already encode entry vs exit three times over); the chart **opens on a recent window** (`DEFAULT_BARS_VISIBLE` — 250 daily / 156 weekly / 120 monthly) rather than all 15 years, with full history one zoom-out away; and a **"Show trade markers" toggle** gives a bare price chart in one click.
2. **Chart legend** (`.chart-legend`) naming the arrows, the 20-week average line, and the filled/hollow candle convention — none of which a beginner could previously infer, and the filled/hollow rule is load-bearing (it's the Phase 4 colourblind mitigation).
3. **Signal-state colour coding** via a shared `app/static/js/signal_style.js` (`signalStateMarkup`, `summaryStateMarkup`), used by the stock page, screener and watchlist so a state looks the same everywhere. **Two project rules constrain this and must not be relaxed:** every state pairs its colour with a **shape** (▲ ● ▼ ◆ ·) because Phase 4's colourblind simulation found forest green and oxblood collapse together under deuteranopia, so colour alone would fail a check this project already made; and **brass is never used** for a computed state, since it's reserved for the AI/margin voice and mixing it in blurs the ink-vs-annotation distinction the design rests on. Attention states (ARMED/DEVELOPING) therefore use bold ink + ◆, not brass.
4. **"Where <stock> stands today" summary** at the top of each stock page — one colour-coded line per system with a short factual descriptor, so the reading comes before the working. Costs **no extra requests**: each loader echoes state it already fetched into its row. Cup & Handle keeps its own quiet styling rather than green/oxblood, preserving the Phase 13 honesty requirement that fuzzy detection never reads as definite. Rows fall back to plain text on short history or a failed load (verified by aborting every API request).
5. **System 1 explainer** — it was the only system on the page that never said what it does; Value Buy and Cup & Handle already had one.
6. **Position size calculator** (`app/static/js/position_size.js`) — listed as a feature in this file since the start but **never actually built** until now. `shares = floor((capital x risk%) / (entry - stop))`, capped by capital when a tight stop would size a position larger than the account. Entry/stop pre-fill from the latest weekly close and the 20-week average (System 1's real stop level) so it opens with concrete numbers. Deliberately **client-side**: it operates only on numbers the user typed, touches no market data, and recalculates per keystroke, so a server round trip would add latency for no correctness gain — and the working is shown on screen so the figure can be checked by hand. Verified against hand calculation (100,000 at 2%, entry 100 / stop 90 → 200 shares, ₹20,000) plus the capped, zero-share, stop>=entry and negative-input cases.

**Boundary held, and worth restating before anyone builds "AI stock picking":** the user asked about robo-advisors that decide where to invest. That would contradict the disclaimer on every page ("not financial advice… not a recommendation to buy or sell") and the Phase 9 AI guardrails that deliberately decline buy/sell/hold questions. This was raised with the user rather than quietly built toward. What was delivered instead is the genuinely useful, opinion-free half of that idea — the risk arithmetic most beginners get wrong. **If a recommender is ever wanted, it is a product/positioning decision about the disclaimers first, not a feature to bolt on.**


## Portfolio holdings view (2026-08-07)

The first robo-advisor-adjacent item that was genuinely missing rather than a presentation fix: the journal recorded real trades but never told the user where they actually stand.

**Cost basis method: FIFO** — confirmed with the user before writing any code, since it changes real P&L numbers. The earliest-bought shares are treated as sold first when a sell only closes part of a position. This is also how Indian tax law computes equity capital gains, so the numbers match what a real broker/IT statement would show — not just an engineering default.

- `app/systems/portfolio_holdings.py` — `compute_holdings(entries, current_prices, names)`, pure computation, no DB/HTTP. Sorts entries by `trade_date` (not insertion order) before running FIFO, since a user can log an old trade after a recent one. A SELL for more than is currently held is capped at what actually exists and surfaced as an `inconsistencies` entry rather than silently going negative or crashing.
- `scripts/verify_portfolio_holdings.py` — no "real data" to cross-check against here (a journal is the user's own entered trades, not downloaded history), so this is entirely hand-built scenarios: the exact worked FIFO example shown to the user (10@100 + 5@120, sell 8 → remaining 2@100+5@120, avg cost 800/7=114.29), an oversold entry, a fully-closed position, out-of-order entries, and concentration across multiple holdings. All pass.
- `GET /api/journal/holdings` — reuses the journal's existing entries and the same cached weekly-close loader every other endpoint uses for "current price." States the price's as-of date plainly in the UI copy rather than implying a live quote, since prices here are a one-time download (Phase 1), never live-refreshed.
- **UI**: a "Your holdings" section on the Journal page, above the add-entry form — the reading before the working, same pattern as the stock page's "Where X stands today." Reloads after every add/delete via a shared `loadHoldings()` called from `journal.js`.
- **Verified against the live database**, not mocks: added real test trades to the (genuinely empty) production journal, confirmed every number by hand (7 shares @ ₹12,714.29 avg cost, ₹16,000 realized P&L — exact FIFO arithmetic), tested the oversold-warning path, then deleted all test data. **A real instance of Neon's documented transient-connection flakiness surfaced during cleanup**: 3 of 4 DELETE calls silently failed on the first pass (no error surfaced, they just didn't take effect) and needed a second attempt with explicit status checks. This is the same free-tier characteristic already documented in Phase 10, not a new bug — but worth remembering that a script trusting DELETE responses without checking status can silently leave stale data behind.


## Submission-readiness pass (2026-09-26)

Prompted by the user needing the site working and presentable for a course submission. First step: fixed the chatbot, which the user reported broken.

**Model switched: `gemini-flash-latest` -> `gemini-flash-lite-latest`.** The former was confirmed persistently 503-overloaded on Google's side across multiple separate sessions - not a transient blip, re-tested and still failing each time. `gemini-flash-lite-latest` answered correctly on 3/3 real API calls (~1.2s each), and is itself the same kind of rolling alias (not a dated snapshot) the project already prefers for this exact reason. Re-verified after the switch, through the real HTTP endpoint (not just the provider class): grounded answers with correct real data, the buy/sell/hold advice guardrail, refusal to fabricate data about a stock outside the 5 seed tickers, and multi-turn context all still hold.

**Separately found, needs the user's action - not a code fix:** the live server currently reports "AI is not configured on this server (no API key set)" and the database still returns 503 "isn't configured", the same as the DB finding from the portfolio-holdings round. Both `GEMINI_API_KEY` and `DATABASE_URL` appear to be missing from Render's environment right now. This can't be diagnosed or fixed from here - no dashboard access - flagged to the user to check Render's Environment tab.


**Home page redesign (same round).** The home page was a bare title and a plain bulleted link list - the user's word for it was "bland." Rebuilt as: a hero section stating the "algorithms calculate, AI explains" philosophy in prose up front (not just the header tagline); a live preview grid of all 5 stocks showing current price, Trend Following state, and Value Buy state, colour-coded via the existing shared `signal_style.js` (same module the stock page/screener/watchlist already use, so a state looks identical everywhere); and an "Explore" grid linking to the Screener/Portfolio/Watchlist/Journal with a one-line description each.

Design constraint respected: this project's own rule is "no drop shadows, no floating cards - paper doesn't have shadows." The new `.tile-grid`/`.tile` CSS is deliberately NOT card-styled - ruled cells divided by hairlines, like a printed ledger's own grid lines, consistent with the rest of the site rather than a new visual language.

Data reuse, not a new endpoint: the stock preview grid calls the existing `/api/screener` (same call the Screener page makes) - `app/static/js/home.js` just writes the result into the tiles. Home page now also gets the splash cover (previously deliberately skipped, since the old page rendered instantly with nothing to hide - now it has real data loading in, so the same treatment applies).

Verified: real API data renders correctly (Maruti's actual NEUTRAL-developing state, Infosys's actual ARMED state), zero console errors, zero horizontal overflow desktop and 375px mobile.


**Full feature sweep (same round), against a locally-configured environment with both AI and DB working.** 30 checks across every page and every interactive element: all 6 pages load with zero console errors and zero horizontal overflow; the 404 page renders styled, not raw JSON; on the stock page, all three systems' signal panels populate, timeframe switching, the markers toggle, capital-driven backtest recompute, and the position size calculator (verified against hand calculation again: 200 shares) all work; the AI chat produces a real reply through the actual UI, not just the API; the portfolio page recomputes on capital change; screener filters narrow results; watchlist add/remove and journal add/delete both persist and clean up correctly against the real database, with the holdings view correctly reflecting a new entry's FIFO cost basis and unrealized P&L.

Three checks initially reported FAIL and were re-run with polling instead of a fixed wait before being trusted - all three turned out to be the test script racing ahead of Neon's own documented multi-second write latency (Phase 10), not real bugs; `journal.js` already calls `loadHoldings()` after both add and delete, confirmed by reading the source before assuming otherwise. One genuine process lesson from this, not a product bug: the first sweep's automated "cleanup" check passed even though nothing had been removed yet (the table was still empty when it looked for a remove button to click, so there was nothing to click) - twice left a real `BAJAJ-AUTO.NS` row sitting in the live watchlist, caught only by directly querying the API afterward rather than trusting the UI-based check, and deleted both times before moving on. Reinforces the project's standing rule: verify cleanup with a direct query, never take the test script's own report of success at face value.
