# InvestIQ AI

**Live site:** https://investiq-ai-l6yf.onrender.com

An AI-assisted investment research platform for five NSE-listed Indian stocks (Maruti Suzuki, Reliance, Infosys, HDFC Bank, Bajaj Auto), built around three rule-based trading systems taken from real handwritten trading notes, and a conversational AI layer that explains — but never generates — the numbers.

Built as a mini project for the subject **AI**, to demonstrate a working, real-world integration of a large language model into a genuinely useful product, not a toy chatbot bolted onto an unrelated app.

---

## The core idea

> **Algorithms calculate. AI explains.**

Every price, indicator, signal, and backtest result on this site is produced by deterministic, auditable Python code — never by the AI. The AI (Google Gemini) is used *only* to explain results that have already been computed elsewhere, in plain language. It is architecturally incapable of inventing a number, because it never receives raw price data — only a compact summary of values that were already calculated before the AI ever saw them.

This isn't a design suggestion, it's enforced by the code: `app/ai_context.py` builds the AI's entire knowledge of a stock from already-computed values, and the AI's system prompt hard-codes rules like *"never fabricate a number,"* *"never tell the user to buy, sell, or hold,"* and *"if asked about anything outside the given data, say plainly that you don't have it."* These guardrails are verified against real API calls, not assumed — see [`scripts/`](scripts/).

The UI also makes this distinction visually obvious: computed values are shown in black ink, serif type, in the main column; anything AI-written sits in a separate margin column, in a different typeface and colour (brass), like a printed ledger annotated by hand — so "computed by algorithm" versus "interpreted by AI" is never ambiguous at a glance.

## What it does

- **Three rule-based trading systems**, each transcribed from the author's own handwritten trading notes:
  - **Trend Following** — RSI(14) + 20-week moving average crossover system
  - **Value Buy** — a technical pullback entry (monthly RSI context, weekly trigger, a pending stop-buy order)
  - **Cup & Handle** — long-term chart-pattern detection; deliberately never shown as an automatic signal, since geometric pattern detection is inherently fuzzy — a human must confirm a detected pattern before any entry math is shown
- **Honest backtesting** — every backtest reports not just the return, but the **maximum drawdown**, the **longest losing streak**, and a **buy-and-hold benchmark computed over the identical period**. The real, disclosed finding: the Trend Following system underperformed simply buying and holding on all five stocks over 2011–2026 — reported plainly rather than hidden, including to the AI itself.
- **An AI chat** on every stock page, grounded only in that stock's already-computed data, that explains signals in plain language and explicitly declines to give investment advice.
- **A stock screener** across all 5 stocks with live filters.
- **A watchlist** and a **personal trade journal** — the journal computes your actual current holdings, cost basis (FIFO), and unrealized profit/loss from trades you log, kept explicitly separate from the hypothetical backtests.
- **A position size calculator** — given your capital, risk tolerance, entry and stop price, tells you exactly how many shares that risk budget allows. Pure arithmetic, explicitly not a recommendation.

## What it deliberately does not do

It never tells you to buy or sell a stock, and it never predicts future prices. This is a boundary held on purpose, not a missing feature — a stock-picking recommender was considered and explicitly rejected, because it would contradict the app's own disclaimers and the AI's guardrails. The site gives you the facts and the arithmetic; the decision stays yours.

## Tech stack

| Layer | Choice |
|---|---|
| Backend | Python, FastAPI |
| Frontend | Server-rendered HTML/Jinja2 + vanilla JavaScript (no framework) |
| Charts | TradingView Lightweight Charts |
| Database | Neon (serverless Postgres, free tier) — watchlist & journal only |
| AI | Google Gemini (`gemini-flash-lite-latest`), via a swappable one-file provider interface |
| Hosting | Render (free tier) |
| Data | 15 years of daily price history for 5 NSE stocks, downloaded once from Yahoo Finance, split-adjusted |

Everything runs on free tiers — ₹0 total cost.

## Running it locally

```
git clone <this repo>
cd investiq
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in your own `GEMINI_API_KEY` (free at [aistudio.google.com](https://aistudio.google.com)) and `DATABASE_URL` (free at [neon.tech](https://neon.tech)) — both optional; the app runs fully without either, degrading gracefully (the AI chat and the watchlist/journal simply show a clear "not configured" message instead).

Then double-click `start.bat`, or run:

```
uvicorn app.main:app --reload
```

## Verification

Every deterministic calculation (indicators, signals, backtests, position sizing, FIFO cost basis) has an independent verification script in [`scripts/`](scripts/) that cross-checks the production code against a from-scratch reimplementation and a set of hand-built scenarios, before being trusted. AI behaviour (grounding, guardrails, guardrail refusals) is verified against real API calls, never mocked.

## Project notes

[`CLAUDE.md`](CLAUDE.md) is a detailed, phase-by-phase engineering log kept throughout development — every design decision, every bug found and fixed, and the reasoning behind each. It's written as a working document for continuing the build across sessions, not as a presentation piece, but it's the most complete record of how and why this project was built the way it was.
