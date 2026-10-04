/* Position size calculator. Arithmetic, not a recommendation.
     shares = floor((capital x risk%) / (entry - stop)),
   capped so the position's value (shares x entry) never exceeds the capital.
   Check: Rs 1,00,000 at 2%, entry 100, stop 90 -> 200 shares, Rs 20,000.
   Recalculates on every keystroke and always shows its working. */
(function () {
  "use strict";

  function parse(text) {
    var t = String(text).replace(/,/g, "").trim();
    if (t === "" || !/^-?\d*\.?\d+$/.test(t)) return NaN;
    return Number(t);
  }

  /* Pure calculation, exposed for checking. Returns {ok, message} or {ok, shares, ...}. */
  function calculate(capital, riskPct, entry, stop) {
    var names = [["capital", capital], ["risk", riskPct], ["entry price", entry], ["stop price", stop]];
    for (var i = 0; i < names.length; i++) {
      if (!isFinite(names[i][1])) return { ok: false, message: "Enter the " + names[i][0] + " as a number." };
    }
    if (capital <= 0) return { ok: false, message: "Capital must be more than zero." };
    if (riskPct <= 0) return { ok: false, message: "Risk per trade must be more than 0%." };
    if (riskPct > 100) return { ok: false, message: "Risk per trade cannot be more than 100% of capital." };
    if (entry <= 0) return { ok: false, message: "The entry price must be more than zero." };
    if (stop < 0) return { ok: false, message: "The stop price cannot be negative." };
    if (stop >= entry) {
      return { ok: false, message: "The stop must be below the entry price: this calculation is for a stop that limits a loss on a purchase. (Right now the stop is " +
        (stop === entry ? "equal to" : "above") + " the entry.)" };
    }
    var riskAmount = capital * riskPct / 100;
    var perShare = entry - stop;
    var byRisk = Math.floor(riskAmount / perShare + 1e-9);
    var byCapital = Math.floor(capital / entry + 1e-9);
    var shares = Math.min(byRisk, byCapital);
    return {
      ok: true, riskAmount: riskAmount, perShare: perShare, byRisk: byRisk, byCapital: byCapital,
      shares: shares, capped: byCapital < byRisk, value: shares * entry, maxLoss: shares * perShare,
    };
  }

  window.PositionSize = { calculate: calculate };

  var form = document.getElementById("calc-form");
  var out = document.getElementById("calc-result");
  if (!form || !out) return;

  function money(n) {
    return "₹" + Number(n).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  function fig(text) { return '<span class="figure">' + text + "</span>"; }

  function render() {
    var capital = parse(form.querySelector("#calc-capital").value);
    var risk = parse(form.querySelector("#calc-risk").value);
    var entry = parse(form.querySelector("#calc-entry").value);
    var stop = parse(form.querySelector("#calc-stop").value);
    var r = calculate(capital, risk, entry, stop);
    if (!r.ok) {
      out.innerHTML = '<p class="form-error" role="alert">' + r.message + "</p>";
      return;
    }
    var working = [
      "Amount at risk = " + fig(money(capital)) + " &times; " + fig(risk + "%") + " = " + fig(money(r.riskAmount)),
      "Risk per share = " + fig(money(entry)) + " &minus; " + fig(money(stop)) + " = " + fig(money(r.perShare)),
      "Shares by risk = floor(" + fig(money(r.riskAmount)) + " &divide; " + fig(money(r.perShare)) + ") = " + fig(r.byRisk),
    ];
    if (r.capped) {
      working.push("Capped by capital: floor(" + fig(money(capital)) + " &divide; " + fig(money(entry)) + ") = " + fig(r.byCapital) +
        ", so the position never costs more than the capital");
    }
    working.push("Position value = " + fig(r.shares) + " &times; " + fig(money(entry)) + " = " + fig(money(r.value)));
    working.push("Loss if the stop is hit = " + fig(r.shares) + " &times; " + fig(money(r.perShare)) + " = " + fig(money(r.maxLoss)));
    var headline = r.shares === 0
      ? '<p class="form-error" role="alert">0 shares: with these numbers not even one share fits, because one share would risk ' +
        money(r.perShare) + ", more than the " + money(r.riskAmount) + " allowed (or costs more than the capital).</p>"
      : '<p class="calc-shares">' + fig(r.shares) + " shares, a position of " + fig(money(r.value)) + "</p>";
    out.innerHTML = headline + '<ul class="calc-working">' + working.map(function (w) { return "<li>" + w + "</li>"; }).join("") + "</ul>";
  }

  form.addEventListener("input", render);
  form.addEventListener("submit", function (e) { e.preventDefault(); });
  render();
})();
