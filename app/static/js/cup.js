/* Cup & Handle (System 2) on the stock page. The detector's output is only ever a POSSIBLE
   formation; price levels appear only after a human confirms it. Every figure comes from the
   server, and the status is fetched with cache "no-store" because confirming changes it. */
(function () {
  "use strict";

  var root = document.getElementById("cup");
  if (!root || !window.Api || !window.BacktestView || typeof LightweightCharts === "undefined") return;
  var BV = window.BacktestView;
  var esc = window.Api.escapeHtml;
  var symbol = root.dataset.symbol;
  var statusEl = document.getElementById("cup-status");
  var noteEl = document.getElementById("cup-note");
  var errorEl = document.getElementById("cup-error");
  var bt = root.querySelector(".backtest");
  var capitalInput = bt.querySelector(".capital-input");
  var modeSelect = document.getElementById("cup-mode");
  var capError = bt.querySelector(".form-error");
  var summaryEl = bt.querySelector(".bt-summary-box");
  var btNoteEl = bt.querySelector(".bt-note");
  var tradesEl = bt.querySelector(".bt-trades-box");
  var busyEl = bt.querySelector(".bt-status");
  var chart = new BV.EquityChart(bt.querySelector(".equity-chart"));
  var data = null;
  var currentCapital = null;

  function fig(text) { return '<span class="figure">' + text + "</span>"; }
  function row(label, html) { return '<tr><th scope="row">' + label + "</th><td>" + html + "</td></tr>"; }
  function pctOf(g) { return "+" + Math.round(g * 100) + "%"; }

  function statusHtml(d) {
    if (d.status === "NONE") {
      return '<p class="cup-quiet">No possible cup formation detected in the monthly data up to ' + fig(esc(d.as_of)) + ".</p>";
    }
    var c = d.cup;
    var html = '<p class="cup-quiet cup-possible"><strong>POSSIBLE cup formation &mdash; review the chart</strong></p>' +
      '<table class="readings"><tbody>' +
      row("Left rim", fig(esc(c.left_rim_date)) + " at " + fig(BV.money(c.left_rim_high))) +
      row("Bottom", fig(esc(c.bottom_date)) + " at " + fig(BV.money(c.bottom_low)) + " (" + fig((c.depth * 100).toFixed(1) + "%") + " below the left rim)") +
      row("Right rim", fig(esc(c.right_rim_date)) + " at " + fig(BV.money(c.right_rim_high)) + " (" + fig(c.months) + " months after the left rim)") +
      row("Handle", fig(esc(c.handle_start)) + " to " + fig(esc(c.handle_end)) + ", low " + fig(BV.money(c.handle_low))) +
      "</tbody></table>";
    if (d.confirmed && d.levels) {
      var lv = d.levels;
      var ladder = lv.ladders[modeSelect.value];
      var sells = ladder.sells.length
        ? ladder.sells.map(function (s) { return "sell &#8531; at " + pctOf(s.gain) + " (" + fig(BV.money(s.price)) + ")"; }).join(", ")
        : "no partial sales";
      html += '<p class="cup-confirmed">You confirmed this cup. Levels under the rules:</p><table class="readings"><tbody>' +
        row("Buy point (handle high)", fig(BV.money(lv.buy_point))) +
        row("Stop-buy (+4%)", fig(BV.money(lv.entry)) + (lv.entry_triggered ? " &middot; crossed in the month ending " + fig(esc(lv.entry_date)) : " &middot; not crossed yet")) +
        row("Stop (&minus;24%)", fig(BV.money(lv.stop))) +
        row(esc(modeSelect.options[modeSelect.selectedIndex].text.split(":")[0]) + " ladder", sells + "; " + esc(ladder.stop_rule) + ".") +
        "</tbody></table>";
    } else if (d.db_available) {
      html += '<p><button type="button" class="btn" id="cup-confirm">Confirm this cup</button> ' +
        '<span class="subtle">Confirming records that you reviewed the chart and agree it is a cup. Only then are its levels shown.</span></p>';
    } else {
      html += '<p class="inline-error">Confirming a cup needs the database, which isn’t configured, so its levels cannot be shown.</p>';
    }
    return html;
  }

  var extraColumns = [
    { label: "Left rim", cell: function (t) { return fig(esc(t.left_rim_date)); } },
    { label: "Stop", cell: function (t) { return fig(BV.money(t.stop)); } },
    { label: "Sales", cell: function (t) {
        return t.tranches.map(function (p) {
          var part = Math.abs(p.fraction - 1) < 1e-6 ? "all" : (Math.abs(p.fraction - 1 / 3) < 1e-4 ? "&#8531;" : (p.fraction * 100).toFixed(0) + "%");
          return part + " " + esc(p.reason) + (p.exit_date ? " " + fig(esc(p.exit_date)) : "");
        }).join("<br>");
      } },
  ];

  function showMode() {
    if (!data) return;
    var b = data.backtests[modeSelect.value];
    summaryEl.innerHTML = BV.summaryHtml(b.summary, { unit: "months" });
    BV.showNote(btNoteEl, b.note);
    tradesEl.innerHTML = BV.tradesHtml(b.trades, "No Cup & Handle setups occurred in this stock's history.",
      { extraColumns: extraColumns, periodLabel: "month ending" });
    chart.setData(b.equity, b.buy_hold);
    statusEl.innerHTML = statusHtml(data);   // the confirmed levels follow the chosen ladder
  }

  async function load(capital, isCurrent) {
    currentCapital = capital;
    busyEl.textContent = "Calculating…";
    try {
      var d = await window.Api.get("/api/stocks/" + encodeURIComponent(symbol) + "/cup-pattern?capital=" + encodeURIComponent(capital));
      if (isCurrent && !isCurrent()) return;
      data = d;
      BV.showNote(noteEl, d.note);
      showMode();
      if (window.InvestIQ) window.InvestIQ.publish("cup", { ok: true, data: d });
    } catch (err) {
      if (isCurrent && !isCurrent()) return;
      statusEl.innerHTML = '<p class="inline-error" role="alert">Could not load the Cup &amp; Handle reading. ' + esc(err.message) + "</p>";
      if (window.InvestIQ) window.InvestIQ.publish("cup", { ok: false });
      summaryEl.innerHTML = "";
      tradesEl.innerHTML = "";
      BV.showNote(noteEl, null);
      BV.showNote(btNoteEl, null);
    } finally {
      if (!isCurrent || isCurrent()) busyEl.textContent = "";
    }
  }

  statusEl.addEventListener("click", async function (event) {
    var button = event.target.closest("#cup-confirm");
    if (!button) return;
    errorEl.hidden = true;
    try {
      // no request body: the server recomputes the cup it is confirming
      await window.Api.withBusy(button, "Adding…", function () {
        return window.Api.post("/api/stocks/" + encodeURIComponent(symbol) + "/cup-pattern/confirm");
      });
      await load(currentCapital);
    } catch (err) {
      errorEl.textContent = err.message;
      errorEl.hidden = false;
    }
  });

  modeSelect.addEventListener("change", showMode);
  BV.bindCapital(capitalInput, capError, load);
})();
