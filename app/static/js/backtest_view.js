/* Shared drawing for backtests: a capital input, a summary table, a trade log and an equity
   curve. Used by every system's backtest and by /portfolio, so they all read the same way.
   All figures come from the server; nothing is calculated here except formatting. */
(function () {
  "use strict";

  var COLORS = { paper: "#f5f1e6", ink: "#1a1a1a", hairline: "rgba(26, 26, 26, 0.18)" };
  var MONO = '"IBM Plex Mono", Consolas, "Courier New", monospace';

  function money(n) {
    return "₹" + Number(n).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  function moneyPlain(n) {
    return Number(n).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  function pct(fraction) {
    var v = fraction * 100;
    return (v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(v).toFixed(2) + "%";
  }
  function escapeHtml(text) {
    return String(text).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  /* A return with a shape AND a sign AND a colour, so colour is never the only cue. */
  function returnMarkup(fraction) {
    if (fraction > 0) {
      return '<span class="ret ret-up"><svg class="ret-shape" viewBox="0 0 12 12" aria-hidden="true"><polygon points="6,1 11.2,10.8 0.8,10.8"/></svg>' + pct(fraction) + "</span>";
    }
    if (fraction < 0) {
      return '<span class="ret ret-down"><svg class="ret-shape" viewBox="0 0 12 12" aria-hidden="true"><polygon points="0.8,1.2 11.2,1.2 6,11"/></svg>' + pct(fraction) + "</span>";
    }
    return '<span class="ret">' + pct(fraction) + "</span>";
  }

  function figure(text) {
    return '<span class="figure">' + text + "</span>";
  }

  /* Summary: the strategy's return right beside buy-and-hold over the identical period. */
  function summaryHtml(s, opts) {
    opts = opts || {};
    var rows = [];
    rows.push('<tr><th scope="col"></th><th scope="col">This system</th><th scope="col">Buy and hold</th></tr>');
    rows.push("<tr><th scope=\"row\">Total return</th><td>" + returnMarkup(s.total_return) + "</td><td>" + returnMarkup(s.buy_hold_return) + "</td></tr>");
    rows.push("<tr><th scope=\"row\">Final value</th><td>" + figure(money(s.final_equity)) + "</td><td>" + figure(money(s.buy_hold_final)) + "</td></tr>");
    rows.push("<tr><th scope=\"row\">Maximum drawdown</th><td>" + figure(pct(s.max_drawdown)) + "</td><td class=\"muted\">&ndash;</td></tr>");
    var table = '<div class="table-scroll"><table class="bt-summary"><tbody>' + rows.join("") + "</tbody></table></div>";

    var facts = [];
    facts.push("Period: " + figure(s.period_start) + " to " + figure(s.period_end) + " (the same " + (opts.unit || "weeks") + " for both columns).");
    if (s.closed_trades !== undefined) {
      facts.push("Closed trades: " + figure(s.closed_trades) +
        (s.closed_trades ? " (" + figure(s.wins) + " won, " + figure(s.losses) + " lost, win rate " + figure((s.win_rate * 100).toFixed(0) + "%") + ")." : "."));
      facts.push("Longest losing streak: " + figure(s.longest_losing_streak) + " closed trade" + (s.longest_losing_streak === 1 ? "" : "s") + " in a row.");
    }
    if (s.open_trade) {
      facts.push("Still open at the end of the data: bought " + figure(s.open_trade.entry_date) + " at " + figure(money(s.open_trade.entry_price)) +
        ", valued at the last close " + figure(money(s.open_trade.marked_price)) + " (" + returnMarkup(s.open_trade.unrealised_return) +
        " unrealised). This open position is included in the final value but not in the closed-trade figures.");
    } else if (s.closed_trades !== undefined) {
      facts.push("No position was open at the end of the data.");
    }
    if (opts.extraFacts) facts = facts.concat(opts.extraFacts);
    return table + '<ul class="bt-facts">' + facts.map(function (f) { return "<li>" + f + "</li>"; }).join("") + "</ul>";
  }

  /* opts.extraColumns: [{ label, cell: function (trade) -> html }] shown before Return. */
  function tradesHtml(trades, emptyText, opts) {
    if (!trades.length) return '<p class="empty-state">' + escapeHtml(emptyText) + "</p>";
    var extra = (opts && opts.extraColumns) || [];
    var period = (opts && opts.periodLabel) || "week ending";
    var head = "<tr><th scope=\"col\">#</th><th scope=\"col\">Bought (" + period + ")</th><th scope=\"col\">Buy price</th>" +
      "<th scope=\"col\">Sold (" + period + ")</th><th scope=\"col\">Sell price</th>" +
      extra.map(function (c) { return '<th scope="col">' + c.label + "</th>"; }).join("") +
      "<th scope=\"col\">Return</th></tr>";
    var body = trades.map(function (t, i) {
      var sold = t.open ? '<span class="open-tag">still open</span>' : figure(t.exit_date);
      var sellPrice = t.open ? figure(money(t.exit_price)) + ' <span class="muted">(last close)</span>' : figure(money(t.exit_price));
      return "<tr><td>" + figure(i + 1) + "</td><td>" + figure(t.entry_date) + "</td><td>" + figure(money(t.entry_price)) +
        "</td><td>" + sold + "</td><td>" + sellPrice + "</td>" +
        extra.map(function (c) { return "<td>" + c.cell(t) + "</td>"; }).join("") +
        "<td>" + returnMarkup(t["return"]) + "</td></tr>";
    }).join("");
    return '<div class="table-scroll"><table class="trade-log"><thead>' + head + "</thead><tbody>" + body + "</tbody></table></div>";
  }

  /* Equity curve: this system (solid ink) against buy-and-hold (dotted ink). */
  function EquityChart(el) {
    this.chart = LightweightCharts.createChart(el, {
      autoSize: true,
      layout: { background: { type: "solid", color: COLORS.paper }, textColor: COLORS.ink, fontFamily: MONO, fontSize: 12 },
      grid: { vertLines: { color: COLORS.hairline }, horzLines: { color: COLORS.hairline } },
      rightPriceScale: { borderColor: COLORS.hairline, minimumWidth: 76 },
      // ~800 weekly points must fit a phone-width chart; the default minimum spacing of
      // 0.5 px per bar would silently cut off the early years.
      timeScale: { borderColor: COLORS.hairline, minBarSpacing: 0.05 },
      localization: { priceFormatter: moneyPlain },
      handleScroll: false,
      handleScale: false,
    });
    this.strategy = this.chart.addLineSeries({ color: COLORS.ink, lineWidth: 2, priceLineVisible: false, lastValueVisible: true });
    this.buyHold = this.chart.addLineSeries({
      color: COLORS.ink, lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Dotted,
      priceLineVisible: false, lastValueVisible: false,
    });
  }
  EquityChart.prototype.setData = function (equity, buyHold) {
    this.strategy.setData(equity);
    this.buyHold.setData(buyHold);
    this.chart.timeScale().fitContent();
  };

  /* Read the capital box. Returns a number, or null after showing why it can't be used. */
  function readCapital(input, errorEl) {
    var raw = String(input.value).replace(/,/g, "").trim();
    var value = Number(raw);
    var problem = null;
    if (raw === "" || !isFinite(value)) problem = "Enter the starting capital as a number, for example 100000.";
    else if (value <= 0) problem = "Capital must be more than zero.";
    else if (value > 1e13) problem = "That amount is too large to be meaningful here.";
    errorEl.textContent = problem || "";
    errorEl.hidden = !problem;
    input.setAttribute("aria-invalid", problem ? "true" : "false");
    return problem ? null : value;
  }

  /* Fetch JSON, turning every failure into an Error with a readable message. */
  async function getJson(url) {
    var res;
    try {
      res = await fetch(url);
    } catch (e) {
      throw new Error("The app's server could not be reached. Check that the InvestIQ window opened by start.bat is still running.");
    }
    var body = null;
    try { body = await res.json(); } catch (e) { /* not JSON */ }
    if (!res.ok) throw new Error((body && typeof body.detail === "string" && body.detail) || "The server answered with an error (" + res.status + ").");
    return body;
  }

  /* Wire a capital box to a loader: recalculates as the user types (after a short pause),
     ignoring answers that arrive out of order. */
  function bindCapital(input, errorEl, load) {
    var timer = null;
    var latest = 0;
    function run() {
      var capital = readCapital(input, errorEl);
      if (capital === null) return;
      var ticket = ++latest;
      load(capital, function isCurrent() { return ticket === latest; });
    }
    input.addEventListener("input", function () {
      clearTimeout(timer);
      timer = setTimeout(run, 350);
    });
    run();
  }

  /* Put a server-written margin note in place (plain text only), or hide the margin. */
  function showNote(el, text) {
    if (!el) return;
    el.textContent = text || "";
    el.hidden = !text;
  }

  window.BacktestView = {
    showNote: showNote,
    money: money,
    pct: pct,
    returnMarkup: returnMarkup,
    summaryHtml: summaryHtml,
    tradesHtml: tradesHtml,
    EquityChart: EquityChart,
    bindCapital: bindCapital,
    getJson: getJson,
    escapeHtml: escapeHtml,
  };
})();
