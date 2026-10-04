/* Trend Following (System 1) on the stock page: shows the current reading and hands the
   BUY / SELL bars to chart.js (through the "system1:loaded" event) to draw as arrows.
   Every number was calculated on the server; this file only displays it. */
(function () {
  "use strict";

  var section = document.querySelector(".chart-section");
  var box = document.getElementById("system1-current");
  if (!section || !box) return;
  var symbol = section.dataset.symbol;

  function money(n) {
    return "₹" + Number(n).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  function row(label, valueHtml) {
    return '<tr><th scope="row">' + label + "</th><td>" + valueHtml + "</td></tr>";
  }

  function render(data) {
    var cur = data.current;
    if (!cur) {
      box.innerHTML = '<p class="subtle">There is not enough weekly history yet to evaluate this system.</p>';
      return;
    }
    var position = cur.in_position
      ? "Open since the week ending " + cur.since
      : "Flat (no open position)";
    box.innerHTML =
      '<table class="readings"><tbody>' +
      row("Week ending", '<span class="figure">' + cur.week_ending + "</span>") +
      row("Signal", window.SignalStyle.signalStateMarkup(cur.state, cur.developing)) +
      row("Position", position.replace(/(\d{4}-\d{2}-\d{2})/, '<span class="figure">$1</span>')) +
      row("Closing price", '<span class="figure">' + money(cur.close) + "</span>") +
      row("20-week average", '<span class="figure">' + money(cur.sma) + "</span>") +
      row("RSI(14)", '<span class="figure">' + cur.rsi.toFixed(2) + "</span>") +
      "</tbody></table>";
  }

  async function load() {
    try {
      var res = await fetch("/api/stocks/" + encodeURIComponent(symbol) + "/system1");
      var body = null;
      try { body = await res.json(); } catch (e) { /* not JSON */ }
      if (!res.ok) throw new Error((body && body.detail) || "The server answered with an error (" + res.status + ").");
      render(body);
      var note = document.getElementById("system1-note");
      if (note && body.note) {
        note.textContent = body.note;
        note.hidden = false;
      }
      window.dispatchEvent(new CustomEvent("system1:loaded", { detail: body }));
      if (window.InvestIQ) window.InvestIQ.publish("system1", { ok: true, data: body });
    } catch (err) {
      if (window.InvestIQ) window.InvestIQ.publish("system1", { ok: false });
      var reason = err instanceof TypeError
        ? "The app's server could not be reached."
        : (err && err.message ? err.message : "");
      box.innerHTML = '<p class="inline-error" role="alert">Could not load the Trend Following reading. ' + reason + "</p>";
    }
  }
  load();
})();
