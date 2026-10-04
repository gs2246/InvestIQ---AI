/* /watchlist: the stocks being watched, each with both systems' current state. */
(function () {
  "use strict";

  var table = document.getElementById("watch-table");
  var form = document.getElementById("watch-add");
  var select = document.getElementById("watch-symbol");
  var errorEl = document.getElementById("watch-error");
  if (!table || !window.Api || !window.SignalStyle) return;
  var esc = window.Api.escapeHtml;

  function showError(message) {
    errorEl.textContent = message || "";
    errorEl.hidden = !message;
  }

  function valueBuyMarkup(vb) {
    var html = window.SignalStyle.signalStateMarkup(vb.state, false);
    if (vb.state === "SELL" && vb.exit_reason) html += ' <span class="subtle">(' + vb.exit_reason + ")</span>";
    return html;
  }

  function render(items) {
    if (!items.length) {
      table.innerHTML = '<p class="empty-state">Your watchlist is empty. Add a stock above, or use the watchlist button on any stock page.</p>';
      return;
    }
    var rows = items.map(function (it) {
      var s1 = it.system1 ? window.SignalStyle.signalStateMarkup(it.system1.state, it.system1.developing) : "&ndash;";
      return "<tr><td><a href=\"/stock/" + encodeURIComponent(it.symbol) + "\">" + esc(it.name) + "</a></td>" +
        '<td><span class="figure">' + esc(it.week_ending) + "</span></td>" +
        "<td>" + s1 + "</td><td>" + valueBuyMarkup(it.value_buy) + "</td>" +
        '<td><button type="button" class="btn btn-quiet" data-remove="' + esc(it.symbol) + '">Remove</button></td></tr>';
    }).join("");
    table.innerHTML = '<div class="table-scroll"><table class="trade-log"><thead><tr>' +
      '<th scope="col">Stock</th><th scope="col">Week ending</th><th scope="col">Trend Following</th>' +
      '<th scope="col">Value Buy</th><th scope="col"><span class="visually-hidden">Actions</span></th></tr></thead><tbody>' +
      rows + "</tbody></table></div>";
  }

  async function load() {
    try {
      var data = await window.Api.get("/api/watchlist");
      render(data.items);
    } catch (err) {
      table.innerHTML = '<p class="inline-error" role="alert">' + esc(err.message) + "</p>";
      if (err.status === 503) form.hidden = true;
    }
  }

  form.addEventListener("submit", async function (event) {
    event.preventDefault();
    showError(null);
    var button = form.querySelector("button");
    try {
      await window.Api.withBusy(button, "Adding…", function () {
        return window.Api.post("/api/watchlist", { symbol: select.value });
      });
      await load();
    } catch (err) {
      showError(err.message);
    }
  });

  table.addEventListener("click", async function (event) {
    var button = event.target.closest("[data-remove]");
    if (!button) return;
    showError(null);
    try {
      await window.Api.withBusy(button, "Removing…", function () {
        return window.Api.del("/api/watchlist/" + encodeURIComponent(button.dataset.remove));
      });
      await load();
    } catch (err) {
      showError(err.message);
    }
  });

  load();
})();
