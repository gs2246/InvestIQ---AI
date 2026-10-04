/* Home page tiles: price and both systems' states for each stock, from GET /api/screener. */
(function () {
  "use strict";

  var grid = document.getElementById("stock-tiles");
  var status = document.getElementById("tiles-status");
  if (!grid || !window.Api || !window.SignalStyle) return;

  function money(n) {
    return "₹" + Number(n).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  async function load() {
    try {
      var data = await window.Api.get("/api/screener");
      data.rows.forEach(function (r) {
        var tile = grid.querySelector('[data-symbol="' + r.symbol + '"]');
        if (!tile) return;
        tile.querySelector('[data-field="price"]').textContent = money(r.close);
        tile.querySelector('[data-field="system1"]').innerHTML = r.system1
          ? window.SignalStyle.signalStateMarkup(r.system1.state, r.system1.developing) : "n/a";
        tile.querySelector('[data-field="value_buy"]').innerHTML = window.SignalStyle.signalStateMarkup(r.value_buy.state, false);
      });
      var week = data.rows.length ? data.rows[0].week_ending : "";
      status.textContent = "Weekly close and each system's state for the week ending " + week +
        ". Prices are a one-time download, not live.";
    } catch (err) {
      // the tiles still link to each stock; only the live readings are missing
      grid.querySelectorAll('[data-field="system1"], [data-field="value_buy"]').forEach(function (el) { el.textContent = "unavailable"; });
      grid.querySelectorAll('[data-field="price"]').forEach(function (el) { el.textContent = ""; });
      status.textContent = "The latest readings could not be loaded. " + err.message;
    }
  }
  load();
})();
