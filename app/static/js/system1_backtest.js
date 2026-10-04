/* Trend Following backtest on the stock page (all money hypothetical). */
(function () {
  "use strict";

  var root = document.getElementById("system1-backtest");
  if (!root || !window.BacktestView || typeof LightweightCharts === "undefined") return;
  var BV = window.BacktestView;
  var symbol = root.dataset.symbol;
  var input = root.querySelector(".capital-input");
  var errorEl = root.querySelector(".form-error");
  var summaryEl = root.querySelector(".bt-summary-box");
  var tradesEl = root.querySelector(".bt-trades-box");
  var statusEl = root.querySelector(".bt-status");
  var noteEl = root.querySelector(".bt-note");
  var chart = new BV.EquityChart(root.querySelector(".equity-chart"));

  BV.bindCapital(input, errorEl, async function (capital, isCurrent) {
    statusEl.textContent = "Calculating…";
    try {
      var data = await BV.getJson("/api/stocks/" + encodeURIComponent(symbol) + "/backtest?capital=" + encodeURIComponent(capital));
      if (!isCurrent()) return;
      summaryEl.innerHTML = BV.summaryHtml(data.summary);
      BV.showNote(noteEl, data.note);
      tradesEl.innerHTML = BV.tradesHtml(data.trades, "No Trend Following trades occurred in this stock's history.");
      chart.setData(data.equity, data.buy_hold);
      statusEl.textContent = "";
    } catch (err) {
      if (!isCurrent()) return;
      statusEl.textContent = "";
      BV.showNote(noteEl, null);
      tradesEl.innerHTML = "";
      summaryEl.innerHTML = '<p class="inline-error" role="alert">Could not calculate the backtest. ' + BV.escapeHtml(err.message) + "</p>";
    }
  });
})();
