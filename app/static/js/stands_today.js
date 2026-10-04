/* "Where <stock> stands today": one line per system, built only from data the page has already
   fetched (published by system1.js, value_buy.js and cup.js), so it makes no requests of its own.
   Each line falls back to plain text if that system's data is missing or failed to load. */
(function () {
  "use strict";

  var list = document.querySelector("#stands-today .stands-list");
  if (!list || !window.SignalStyle) return;
  var S = window.SignalStyle;

  function money(n) {
    return "₹" + Number(n).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  function setLine(name, html) {
    var cell = list.querySelector('[data-system="' + name + '"] .stands-desc');
    if (cell) cell.innerHTML = html;
  }
  function plain(text) { return '<span class="stands-quiet">' + window.Api.escapeHtml(text) + "</span>"; }

  function system1(p) {
    if (!p || !p.ok) return plain("Reading unavailable; see the Trend Following section below.");
    var c = p.data.current;
    if (!c) return plain("Not enough weekly history yet.");
    var d;
    if (c.state === "BUY") d = "entry conditions met in the week ending " + c.week_ending;
    else if (c.state === "HOLD") d = "in a position since the week ending " + c.since + "; close still at or above the 20-week average";
    else if (c.state === "SELL") d = "the weekly close (" + money(c.close) + ") fell below the 20-week average (" + money(c.sma) + ")";
    else if (c.developing) d = "no position; conditions building (RSI " + c.rsi.toFixed(2) + " and rising, close above the average)";
    else d = "no position; RSI " + c.rsi.toFixed(2) + ", close " + (c.close >= c.sma ? "above" : "below") + " the 20-week average";
    return S.summaryStateMarkup(c.state, c.developing, d + " (week ending " + c.week_ending + ").");
  }

  function valueBuy(p) {
    if (!p || !p.ok) return plain("Reading unavailable; see the Value Buy section below.");
    var c = p.data.current, d;
    if (c.state === "ARMED") d = "stop-buy armed at " + money(c.armed.level) + ", stop " + money(c.armed.stop);
    else if (c.state === "BUY") d = "stop-buy triggered at " + money(c.position.entry) + "; target " + money(c.position.target);
    else if (c.state === "HOLD") d = "in a position from " + money(c.position.entry) + "; stop " + money(c.position.stop) + ", target " + money(c.position.target);
    else if (c.state === "SELL") d = "position closed at the " + c.exit_reason;
    else d = c.context.active ? "monthly context active; waiting for a green weekly candle" : "monthly context not active (monthly RSI " +
      (c.context.rsi === null ? "n/a" : c.context.rsi.toFixed(2)) + ")";
    return S.summaryStateMarkup(c.state, false, d + ".");
  }

  function cup(p) {
    // Quiet styling on purpose: Cup & Handle output is never a signal badge.
    if (!p || !p.ok) return plain("Reading unavailable; see the Cup & Handle section below.");
    var d = p.data;
    if (d.status === "NONE") return plain("No possible cup formation detected.");
    return plain(d.confirmed ? "Possible cup formation, confirmed by you; levels are in the Cup & Handle section."
      : "Possible cup formation (unconfirmed); review the chart in the Cup & Handle section.");
  }

  var renderers = { system1: system1, value_buy: valueBuy, cup: cup };
  function render(name) {
    if (renderers[name]) setLine(name, renderers[name]((window.InvestIQState || {})[name]));
  }
  // Anything published before this script ran, then everything after.
  Object.keys(renderers).forEach(function (name) { if ((window.InvestIQState || {})[name]) render(name); });
  window.addEventListener("investiq:state", function (e) { render(e.detail.name); });

  // Fallback: if a section's script never reported (it failed to start), say so in plain text
  // instead of leaving a placeholder on screen forever.
  window.addEventListener("load", function () {
    setTimeout(function () {
      Object.keys(renderers).forEach(function (name) {
        if (!(window.InvestIQState || {})[name]) render(name);
      });
    }, 15000);
  });
})();
