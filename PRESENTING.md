# Presenting InvestIQ AI

Notes for demo day. Not part of the app; just for you.

The app now runs on your own laptop, so there is no website to wake up and no hosting settings that can go missing. What matters is that MySQL is running, the app starts, and the laptop has internet for the AI chat.

## 10 minutes before you present

1. **Start the app.** Double-click `start.bat` in the project folder. A black window opens and, a few seconds later, the browser opens `http://localhost:8000`. Keep the black window open the whole time: closing it stops the app.
2. **Open one stock page** (Bajaj Auto is a good one) and wait for the title cover to lift. The chart, the "Where Bajaj Auto stands today" lines and the backtests should all appear.
3. **Ask the chatbot one question** on that page and confirm it replies. The chat is the only part that needs the internet.
4. **Open the Journal page** and confirm it shows "Your holdings" rather than a "database isn't configured" message. That confirms MySQL is running.
5. **Close any other copy of the app.** If the page looks old or odd, an earlier black window may still be running. Close all of them and double-click `start.bat` once.

If something is off:

- **"Database isn't configured" on the Journal or Watchlist:** MySQL is not running. Open **Services** in Windows, find `MySQL80`, and start it. (It is set to start automatically, so this should be rare.) Everything else works without the database anyway.
- **"AI is not configured" or the AI does not answer:** check the internet connection. The key itself lives in your `.env` file. If you ever need a new one, create it at aistudio.google.com and paste it into `.env`, never into a chat.

## Suggested demo flow (about 5 to 7 minutes)

Don't tour every feature. The app is deep (5 stocks, 3 systems, a screener, watchlist, journal, calculator, AI chat), and a short, deliberate sequence tells a better story.

1. **Home page.** Say the philosophy out loud: *"Algorithms calculate, AI explains."* Point at the five tiles showing each stock's price and both systems' states, filled in from the rules.
2. **One stock, one system, in depth: Bajaj Auto.** Its Trend Following signal for the week ending 2 October 2026 is **SELL**: the weekly close (₹10,045) fell below the 20-week average (₹10,876). Show the arrow on the weekly chart sitting exactly where the close crosses the line, the "Where Bajaj Auto stands today" line at the top, and the brass margin note explaining it.
3. **The backtest's honesty: your strongest moment.** Scroll to the Trend Following backtest and show buy-and-hold right beside the strategy's return. Say plainly: *"The strategy underperformed simply holding the stock, on all five stocks, and the site says so instead of hiding it."* (Maruti: +243.9% against +960.0%.) Most projects only show favourable results; this one doesn't, and that is worth saying explicitly.
4. **The AI chat, and its refusal.** Ask something factual ("What is the latest weekly RSI?"), then ask *"Should I buy this stock?"* and let it decline. The AI is not simply being polite: it was never given an opinion to have, only already-computed figures and firm rules.
5. **Cup & Handle, briefly.** Show "No possible cup formation detected" and explain why: on these strongly rising stocks a later high never returns within 8% of an earlier one five or more years before, so the strict rule finds nothing, and the thresholds were not loosened to manufacture a result.
6. **Journal and holdings.** Log a trade (for example BUY 10 at ₹100, BUY 5 at ₹120, SELL 8), show the holdings worked out first in, first out (7 shares at an average cost of ₹114.29), then delete the entries again so your journal stays clean.
7. **Close on the boundary you held.** A "which stock should I buy" recommender was considered and deliberately rejected, because it would contradict the app's own disclaimers. That is a design decision, not a missing feature; say so.

## Things worth knowing if someone asks

- **The prices are not live.** They are a one-time download; the newest completed week is the week ending 2 October 2026. The app says so on every page that shows a price.
- **The backtests use hypothetical money** and ignore brokerage and taxes.
- **Everything is checked:** each calculation has a verification script that compares it with a separate from-scratch version, and the AI's rules were tested with real calls.

## If the live demo breaks anyway

Demos fail sometimes for reasons that have nothing to do with whether the work is good. Either fallback is fine:

- **Screenshots of the flow above**, taken in advance, as a backup slide or two.
- **A short screen recording** (60 to 90 seconds) of the same sequence.

Without the internet, everything except the AI chat still works, because the app and its data are all on your laptop.
