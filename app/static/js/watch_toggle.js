/* The "Add to watchlist / Remove from watchlist" button on a stock page. */
(function () {
  "use strict";

  var box = document.getElementById("watch-toggle");
  if (!box || !window.Api) return;
  var symbol = box.dataset.symbol;
  var button = box.querySelector("button");
  var status = box.querySelector(".watch-status");
  var watching = false;

  function show() {
    button.textContent = watching ? "Remove from watchlist" : "Add to watchlist";
    button.setAttribute("aria-pressed", watching ? "true" : "false");
    status.textContent = watching ? "This stock is on your watchlist." : "";
  }

  async function load() {
    try {
      var data = await window.Api.get("/api/watchlist");
      watching = data.items.some(function (it) { return it.symbol === symbol; });
      button.hidden = false;
      show();
    } catch (err) {
      button.hidden = true;
      status.textContent = err.status === 503
        ? "The watchlist is unavailable because the database isn't configured."
        : "The watchlist could not be loaded. " + err.message;
    }
  }

  button.addEventListener("click", async function () {
    try {
      await window.Api.withBusy(button, watching ? "Removing…" : "Adding…", function () {
        return watching
          ? window.Api.del("/api/watchlist/" + encodeURIComponent(symbol))
          : window.Api.post("/api/watchlist", { symbol: symbol });
      });
      watching = !watching;
      show();
    } catch (err) {
      show();
      status.textContent = err.message;
    }
  });

  load();
})();
