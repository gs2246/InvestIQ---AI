/* Value Buy (System 3) on the stock page: current reading, margin note and backtest.
   Every figure was calculated on the server; this file only displays it. */
(function () {
  "use strict";

  var root = document.getElementById("value-buy");
  if (!root || !window.BacktestView || !window.SignalStyle || typeof LightweightCharts === "undefined") return;
  var BV = window.BacktestView;
  var symbol = root.dataset.symbol;
  var currentEl = document.getElementById("value-buy-current");
  var noteEl = document.getElementById("value-buy-note");
  var bt = root.querySelector(".backtest");
  var input = bt.querySelector(".capital-input");
  var errorEl = bt.querySelector(".form-error");
  var summaryEl = bt.querySelector(".bt-summary-box");
  var btNoteEl = bt.querySelector(".bt-note");
  var tradesEl = bt.querySelector(".bt-trades-box");
  var statusEl = bt.querySelector(".bt-status");
  var chart = new BV.EquityChart(bt.querySelector(".equity-chart"));

  function fig(text) { return '<span class="figure">' + text + "</span>"; }
  function row(label, html) { return '<tr><th scope="row">' + label + "</th><td>" + html + "</td></tr>"; }

  function currentHtml(cur) {
    var signal = window.SignalStyle.signalStateMarkup(cur.state, false);
    if (cur.state === "SELL") signal += ' <span class="subtle">(' + (cur.exit_reason === "stop" ? "stop reached" : "target reached") + ")</span>";
    var ctx = cur.context;
    var ctxText = ctx.rsi === null
      ? "Not enough monthly history yet"
      : "RSI " + fig(ctx.rsi.toFixed(2)) + " for the month ending " + fig(ctx.month) +
        " (previous month " + fig(ctx.prev_rsi === null ? "n/a" : ctx.prev_rsi.toFixed(2)) + "): " +
        "<strong>" + (ctx.active ? "active" : "not active") + "</strong>";
    var rows = [
      row("Week ending", fig(cur.week_ending)),
      row("Signal", signal),
      row("Monthly context", ctxText),
    ];
    if (cur.armed) {
      var a = cur.armed;
      rows.push(row("Signal candle", "green week ending " + fig(a.signal_week)));
      rows.push(row("Stop-buy level", fig(BV.money(a.level)) + ' <span class="subtle">(the signal candle’s high)</span>'));
      rows.push(row("Stop", fig(BV.money(a.stop)) + ' <span class="subtle">(its low)</span>'));
      rows.push(row("Lapses after", fig(a.weeks_left) + " more week" + (a.weeks_left === 1 ? "" : "s") + " without a trigger"));
    }
    if (cur.position) {
      var p = cur.position;
      rows.push(row("Entry", fig(BV.money(p.entry)) + " in the week ending " + fig(p.entry_week)));
      rows.push(row("Stop (fixed)", fig(BV.money(p.stop))));
      rows.push(row("Target (swing high)", fig(BV.money(p.target))));
      rows.push(row("Risk / reward", fig(BV.money(p.risk)) + " / " + fig(BV.money(p.reward)) +
        (p.ratio === null ? "" : ", a ratio of " + fig(p.ratio.toFixed(2)) + " to 1")));
      if (p.exit_price !== undefined) rows.push(row("Closed at", fig(BV.money(p.exit_price))));
    }
    rows.push(row("All-time high", fig(BV.money(cur.all_time_high)) + ' <span class="subtle">(week ending ' + cur.all_time_high_week + "; context only, not the target)</span>"));
    return '<table class="readings"><tbody>' + rows.join("") + "</tbody></table>";
  }

  var extraColumns = [
    { label: "Signal week", cell: function (t) { return fig(t.signal_date); } },
    { label: "Stop", cell: function (t) { return fig(BV.money(t.stop)); } },
    { label: "Target", cell: function (t) { return fig(BV.money(t.target)); } },
    { label: "Reward : risk", cell: function (t) { return t.ratio === null ? "&ndash;" : fig(t.ratio.toFixed(2) + " : 1"); } },
    { label: "Exit", cell: function (t) { return t.open ? "&ndash;" : (t.exit_reason === "stop" ? "stop" : "target"); } },
  ];

  var firstLoad = true;
  BV.bindCapital(input, errorEl, async function (capital, isCurrent) {
    statusEl.textContent = "Calculating…";
    try {
      var data = await BV.getJson("/api/stocks/" + encodeURIComponent(symbol) + "/value-buy?capital=" + encodeURIComponent(capital));
      if (!isCurrent()) return;
      if (firstLoad) {
        currentEl.innerHTML = currentHtml(data.current);
        BV.showNote(noteEl, data.note);
        if (window.InvestIQ) window.InvestIQ.publish("value_buy", { ok: true, data: data });
        firstLoad = false;
      }
      var b = data.backtest;
      summaryEl.innerHTML = BV.summaryHtml(b.summary);
      BV.showNote(btNoteEl, b.note);
      tradesEl.innerHTML = BV.tradesHtml(b.trades, "No Value Buy setups occurred in this stock's history.", { extraColumns: extraColumns });
      chart.setData(b.equity, b.buy_hold);
      statusEl.textContent = "";
    } catch (err) {
      if (!isCurrent()) return;
      statusEl.textContent = "";
      if (firstLoad) {
        currentEl.innerHTML = '<p class="inline-error" role="alert">Could not load the Value Buy reading. ' + BV.escapeHtml(err.message) + "</p>";
        if (window.InvestIQ) window.InvestIQ.publish("value_buy", { ok: false });
      }
      BV.showNote(btNoteEl, null);
      tradesEl.innerHTML = "";
      summaryEl.innerHTML = '<p class="inline-error" role="alert">Could not calculate the Value Buy backtest. ' + BV.escapeHtml(err.message) + "</p>";
    }
  });
})();
