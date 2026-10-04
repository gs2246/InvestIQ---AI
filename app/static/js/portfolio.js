/* /portfolio: Trend Following across all five stocks (all money hypothetical). */
(function () {
  "use strict";

  var root = document.getElementById("portfolio-backtest");
  if (!root || !window.BacktestView || typeof LightweightCharts === "undefined") return;
  var BV = window.BacktestView;
  var input = root.querySelector(".capital-input");
  var errorEl = root.querySelector(".form-error");
  var summaryEl = root.querySelector(".bt-summary-box");
  var stocksEl = root.querySelector(".bt-stocks-box");
  var statusEl = root.querySelector(".bt-status");
  var noteEl = root.querySelector(".bt-note");
  var chart = new BV.EquityChart(root.querySelector(".equity-chart"));

  function stocksHtml(stocks, share) {
    var head = "<tr><th scope=\"col\">Stock</th><th scope=\"col\">Final value</th><th scope=\"col\">This system</th>" +
      "<th scope=\"col\">Buy and hold</th><th scope=\"col\">Max drawdown</th><th scope=\"col\">Closed trades</th>" +
      "<th scope=\"col\">Longest losing streak</th></tr>";
    var body = stocks.map(function (s) {
      return "<tr><td><a href=\"/stock/" + encodeURIComponent(s.symbol) + "\">" + BV.escapeHtml(s.name) + "</a></td>" +
        "<td><span class=\"figure\">" + BV.money(s.final_equity) + "</span></td>" +
        "<td>" + BV.returnMarkup(s.total_return) + "</td><td>" + BV.returnMarkup(s.buy_hold_return) + "</td>" +
        "<td><span class=\"figure\">" + BV.pct(s.max_drawdown) + "</span></td>" +
        "<td><span class=\"figure\">" + s.closed_trades + "</span>" + (s.open_position ? " + 1 open" : "") + "</td>" +
        "<td><span class=\"figure\">" + s.longest_losing_streak + "</span></td></tr>";
    }).join("");
    return '<p class="subtle">Each stock started with <span class="figure">' + BV.money(share) + "</span>.</p>" +
      '<div class="table-scroll"><table class="trade-log"><thead>' + head + "</thead><tbody>" + body + "</tbody></table></div>";
  }

  BV.bindCapital(input, errorEl, async function (capital, isCurrent) {
    statusEl.textContent = "Calculating…";
    try {
      var data = await BV.getJson("/api/portfolio/backtest?capital=" + encodeURIComponent(capital));
      if (!isCurrent()) return;
      summaryEl.innerHTML = BV.summaryHtml(data.summary);
      BV.showNote(noteEl, data.note);
      stocksEl.innerHTML = stocksHtml(data.stocks, data.summary.per_stock_capital);
      chart.setData(data.equity, data.buy_hold);
      statusEl.textContent = "";
    } catch (err) {
      if (!isCurrent()) return;
      statusEl.textContent = "";
      BV.showNote(noteEl, null);
      stocksEl.innerHTML = "";
      summaryEl.innerHTML = '<p class="inline-error" role="alert">Could not calculate the portfolio backtest. ' + BV.escapeHtml(err.message) + "</p>";
    }
  });
})();
