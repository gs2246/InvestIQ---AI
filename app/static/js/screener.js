/* /screener: one table of all five stocks from a single GET /api/screener, filtered in the browser. */
(function () {
  "use strict";

  var body = document.getElementById("screener-body");
  var form = document.getElementById("screener-filters");
  var countEl = document.getElementById("screener-count");
  if (!body || !window.Api || !window.SignalStyle) return;
  var esc = window.Api.escapeHtml;
  var selects = Array.prototype.slice.call(form.querySelectorAll("[data-filter]"));
  var rows = [];
  var weekEnding = "";

  function money(n) {
    return "₹" + Number(n).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  /* Does a row pass one filter? Trend Following's DEVELOPING is a flag on NEUTRAL, not a state. */
  function passes(row, key, value) {
    if (!value) return true;
    if (key === "system1") {
      if (!row.system1) return false;
      return value === "DEVELOPING" ? row.system1.developing : row.system1.state === value;
    }
    if (key === "value_buy") return row.value_buy.state === value;
    return row[key] === value;
  }

  function render() {
    var active = selects.map(function (s) { return [s.dataset.filter, s.value]; });
    var shown = rows.filter(function (r) {
      return active.every(function (f) { return passes(r, f[0], f[1]); });
    });
    if (!shown.length) {
      body.innerHTML = '<tr class="empty-row"><td colspan="7"><p class="empty-state">No stock matches these filters. ' +
        "Try clearing one of them.</p></td></tr>";
    } else {
      body.innerHTML = shown.map(function (r) {
        var vb = window.SignalStyle.signalStateMarkup(r.value_buy.state, false);
        var s1 = r.system1 ? window.SignalStyle.signalStateMarkup(r.system1.state, r.system1.developing) : "&ndash;";
        return "<tr><td><a href=\"/stock/" + encodeURIComponent(r.symbol) + "\">" + esc(r.name) + "</a></td>" +
          '<td><span class="figure">' + money(r.close) + "</span></td>" +
          '<td><span class="figure">' + (r.rsi === null ? "n/a" : r.rsi.toFixed(2)) + "</span></td>" +
          "<td>" + esc(r.rsi_zone || "n/a") + "</td><td>" + esc(r.rsi_trend || "n/a") + "</td>" +
          "<td>" + s1 + "</td><td>" + vb + "</td></tr>";
      }).join("");
    }
    countEl.textContent = "Showing " + shown.length + " of " + rows.length + " stocks, week ending " + weekEnding + ".";
  }

  selects.forEach(function (s) { s.addEventListener("change", render); });
  form.addEventListener("reset", function () { setTimeout(render, 0); }); // after the browser clears the selects

  async function load() {
    try {
      var data = await window.Api.get("/api/screener");
      rows = data.rows;
      weekEnding = rows.length ? rows[0].week_ending : "";
      render();
    } catch (err) {
      body.innerHTML = '<tr><td colspan="7"><p class="inline-error" role="alert">Could not load the screener. ' + esc(err.message) + "</p></td></tr>";
    }
  }
  load();
})();
