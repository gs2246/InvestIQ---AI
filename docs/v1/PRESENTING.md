# Presenting InvestIQ AI

Notes for demo day. Not part of the app — just for you.

## 5 minutes before you present

1. **Open the live site yourself first.** https://investiq-ai-l6yf.onrender.com
   If it's been idle 15+ minutes, the first load takes 30–60 seconds of
   blank waiting (Render's free tier sleeps when idle — this is a known,
   accepted trade-off, not a bug). Opening it yourself beforehand means
   it's already warm when you actually present.
2. **Ask the chatbot one question** on any stock page and confirm it
   replies. This also confirms the database-backed pages (Watchlist,
   Journal) are working — both depend on the same Render environment
   variables, which have gone missing once before without warning.
3. If either is broken: check Render → your service → **Environment**
   tab → confirm `GEMINI_API_KEY` and `DATABASE_URL` are both still
   present. Both values are also sitting safely in your local `.env`
   file if you need to re-paste them.

## Suggested demo flow (~5–7 minutes)

Don't wander through every feature — the site is deep (5 stocks, 3
systems, a screener, watchlist, journal, calculator, AI chat). A short,
deliberate sequence tells a better story than a random tour.

1. **Home page** — state the philosophy out loud: *"algorithms
   calculate, AI explains."* Point at the live stock tiles updating with
   real signals.
2. **One stock, one system, in depth.** Maruti's Trend Following signal
   is a clean example. Show the chart, the current signal, and the
   margin note explaining it in plain language.
3. **The backtest's honesty — your strongest moment.** Scroll to the
   backtest and show the buy-and-hold comparison sitting right next to
   the return. Say plainly: *"the strategy actually underperformed just
   holding the stock, on all five stocks — and the site says so instead
   of hiding it."* Most student projects only show favorable results;
   this one doesn't, and that's worth stating explicitly, not glossing
   over.
4. **The AI chat, and its refusal.** Ask it something factual, then ask
   it *"should I buy this stock?"* and let it decline. That one refusal
   demonstrates the guardrail architecture more convincingly than any
   slide — the AI is not choosing to be polite, it's structurally unable
   to answer that question because it was never given an opinion to
   have.
5. **Journal → Holdings.** Log a trade, show the computed holdings (FIFO
   cost basis, unrealized P&L) — real trade tracking, kept explicitly
   separate from the hypothetical backtests above.
6. **Close on the boundary you held.** State that a "which stock should
   I buy" recommender was considered and deliberately rejected, because
   it would contradict the app's own disclaimers. That's a design
   decision, not a missing feature — say so.

## If the live demo breaks anyway

Software demos fail sometimes, for reasons that have nothing to do with
whether the work is good. Two options, either is fine to fall back on:

- **Screenshots of the flow above**, taken in advance, as a backup slide
  or two.
- **A short screen recording** (60–90 seconds) of the same sequence,
  which you can play if the live site or your internet has a bad
  moment.

Neither is necessary if the live demo goes fine — just don't let a
Render cold start be the first thing anyone sees.
