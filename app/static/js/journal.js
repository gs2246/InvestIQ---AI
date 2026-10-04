/* /journal: real trades (form + table) and the FIFO holdings worked out from them.
   Holdings reload after every add and delete. */
(function () {
  "use strict";

  var form = document.getElementById("journal-form");
  var holdingsBox = document.getElementById("holdings-box");
  var tableBox = document.getElementById("journal-table");
  var errorEl = document.getElementById("journal-error");
  if (!form || !window.Api || !window.BacktestView) return;
  var esc = window.Api.escapeHtml;
  var money = window.BacktestView.money;

  function fig(text) { return '<span class="figure">' + text + "</span>"; }
  function showError(message) {
    errorEl.textContent = message || "";
    errorEl.hidden = !message;
  }

  /* Profit or loss: colour plus a shape and a sign, never colour alone. */
  function pnl(amount) {
    if (amount === null || amount === undefined) return '<span class="muted">n/a</span>';
    var shape = amount > 0 ? '<polygon points="6,1 11.2,10.8 0.8,10.8"/>' : amount < 0 ? '<polygon points="0.8,1.2 11.2,1.2 6,11"/>' : "";
    var cls = amount > 0 ? "ret ret-up" : amount < 0 ? "ret ret-down" : "ret";
    var sign = amount > 0 ? "+" : amount < 0 ? "−" : "";
    return '<span class="' + cls + '">' + (shape ? '<svg class="ret-shape" viewBox="0 0 12 12" aria-hidden="true">' + shape + "</svg>" : "") +
      sign + money(Math.abs(amount)) + "</span>";
  }

  function renderHoldings(data) {
    var open = data.holdings.filter(function (h) { return h.quantity > 0; });
    // "Fully sold" only if shares were actually bought; a stray SELL alone is an inconsistency, not a sale.
    var closed = data.holdings.filter(function (h) { return h.quantity === 0 && h.shares_bought > 0; });
    var html = '<p class="subtle">"Current price" is the latest completed weekly close in the downloaded data, as of ' +
      fig(esc(data.prices_as_of)) + ". Prices are a one-time download, never live.</p>";
    if (!data.holdings.length) {
      html += '<p class="empty-state">No holdings yet. Add a BUY entry below to start.</p>';
    } else {
      if (open.length) {
        html += '<div class="table-scroll"><table class="trade-log"><thead><tr><th scope="col">Stock</th>' +
          '<th scope="col">Shares</th><th scope="col">Average cost</th><th scope="col">Cost basis</th>' +
          '<th scope="col">Current price</th><th scope="col">Market value</th><th scope="col">Unrealised P&amp;L</th>' +
          '<th scope="col">Realised P&amp;L</th></tr></thead><tbody>' +
          open.map(function (h) {
            return "<tr><td>" + esc(h.name) + "</td><td>" + fig(h.quantity) + "</td><td>" + fig(money(h.avg_cost)) +
              "</td><td>" + fig(money(h.cost_basis)) + "</td><td>" + (h.current_price === null ? "n/a" : fig(money(h.current_price))) +
              "</td><td>" + (h.market_value === null ? "n/a" : fig(money(h.market_value))) + "</td><td>" + pnl(h.unrealised_pnl) +
              "</td><td>" + pnl(h.realised_pnl) + "</td></tr>";
          }).join("") + "</tbody></table></div>";
        html += '<p class="totals">Totals for shares still held: cost ' + fig(money(data.totals.cost_basis)) + ", market value " +
          fig(money(data.totals.market_value)) + ", unrealised " + pnl(data.totals.unrealised_pnl) +
          ". Realised on all sales: " + pnl(data.totals.realised_pnl) + ".</p>";
      } else {
        html += '<p class="empty-state">You hold no shares at the moment.</p>';
      }
      if (closed.length) {
        html += '<p class="subtle">Fully sold: ' + closed.map(function (h) {
          return esc(h.name) + " (realised " + pnl(h.realised_pnl) + ")";
        }).join(", ") + ".</p>";
      }
    }
    if (data.inconsistencies.length) {
      html += '<div class="inline-error" role="alert"><strong>Please check these entries:</strong><ul>' +
        data.inconsistencies.map(function (i) { return "<li>" + esc(i.message) + "</li>"; }).join("") + "</ul></div>";
    }
    holdingsBox.innerHTML = html;
  }

  function renderEntries(entries) {
    if (!entries.length) {
      tableBox.innerHTML = '<p class="empty-state">No journal entries yet.</p>';
      return;
    }
    tableBox.innerHTML = '<div class="table-scroll"><table class="trade-log"><thead><tr><th scope="col">Trade date</th>' +
      '<th scope="col">Stock</th><th scope="col">Side</th><th scope="col">Shares</th><th scope="col">Price</th>' +
      '<th scope="col">Value</th><th scope="col">Notes</th><th scope="col"><span class="visually-hidden">Actions</span></th></tr></thead><tbody>' +
      entries.map(function (e) {
        return "<tr><td>" + fig(esc(e.trade_date)) + "</td><td>" + esc(e.name) + '</td><td><span class="side side-' +
          e.side.toLowerCase() + '">' + e.side + "</span></td><td>" + fig(e.quantity) + "</td><td>" + fig(money(e.price)) +
          "</td><td>" + fig(money(e.quantity * e.price)) + '</td><td class="notes-cell">' + esc(e.notes || "") +
          '</td><td><button type="button" class="btn btn-quiet" data-delete="' + e.id + '">Delete</button></td></tr>';
      }).join("") + "</tbody></table></div>";
  }

  async function loadAll() {
    try {
      var results = await Promise.all([window.Api.get("/api/journal/holdings"), window.Api.get("/api/journal")]);
      renderHoldings(results[0]);
      renderEntries(results[1].entries);
    } catch (err) {
      var msg = '<p class="inline-error" role="alert">' + esc(err.message) + "</p>";
      holdingsBox.innerHTML = msg;
      tableBox.innerHTML = "";
      if (err.status === 503) form.hidden = true;
    }
  }

  form.addEventListener("submit", async function (event) {
    event.preventDefault();
    showError(null);
    var body = {
      symbol: form.symbol.value,
      side: form.side.value,
      quantity: form.quantity.value.trim(),
      price: form.price.value.trim(),
      trade_date: form.trade_date.value,
      notes: form.notes.value,
    };
    if (/^\d+$/.test(body.quantity)) body.quantity = Number(body.quantity);
    try {
      await window.Api.withBusy(document.getElementById("j-submit"), "Adding…", function () {
        return window.Api.post("/api/journal", body);
      });
      form.quantity.value = "";
      form.price.value = "";
      form.notes.value = "";
      await loadAll();
    } catch (err) {
      showError(err.message);
    }
  });

  tableBox.addEventListener("click", async function (event) {
    var button = event.target.closest("[data-delete]");
    if (!button) return;
    showError(null);
    try {
      await window.Api.withBusy(button, "Deleting…", function () {
        return window.Api.del("/api/journal/" + encodeURIComponent(button.dataset.delete));
      });
      await loadAll();
    } catch (err) {
      showError(err.message);
    }
  });

  loadAll();
})();
