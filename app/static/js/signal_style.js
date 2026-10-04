/* The one place that decides how a signal state looks, so BUY (etc.) is identical on every page.

   Colour never carries meaning alone: every state pairs a colour with a shape.
     BUY  triangle up   forest        HOLD  circle         forest
     SELL triangle down oxblood
     ARMED / DEVELOPING  diamond      bold ink
     NEUTRAL  small dot               plain ink
   Brass is never used here: it is reserved for the margin / AI voice.

   The shapes are inline SVG, not font glyphs, because IBM Plex has no triangle, circle or
   diamond characters and the browser would borrow them from a different font on each computer. */
(function () {
  "use strict";

  var SHAPES = {
    triangleUp: '<polygon points="6,1 11.2,10.8 0.8,10.8"/>',
    triangleDown: '<polygon points="0.8,1.2 11.2,1.2 6,11"/>',
    circle: '<circle cx="6" cy="6" r="4.6"/>',
    diamond: '<polygon points="6,0.8 11.2,6 6,11.2 0.8,6"/>',
    dot: '<circle cx="6" cy="6" r="1.7"/>',
  };

  var STATES = {
    BUY: { shape: "triangleUp", cls: "signal-buy", label: "BUY" },
    HOLD: { shape: "circle", cls: "signal-hold", label: "HOLD" },
    SELL: { shape: "triangleDown", cls: "signal-sell", label: "SELL" },
    ARMED: { shape: "diamond", cls: "signal-emphasis", label: "ARMED" },
    DEVELOPING: { shape: "diamond", cls: "signal-emphasis", label: "DEVELOPING" },
    NEUTRAL: { shape: "dot", cls: "signal-neutral", label: "NEUTRAL" },
  };

  function one(key) {
    var s = STATES[key];
    if (!s) return '<span class="signal signal-neutral">' + escapeHtml(String(key)) + "</span>";
    return (
      '<span class="signal ' + s.cls + '">' +
      '<svg class="signal-shape" viewBox="0 0 12 12" aria-hidden="true" focusable="false">' + SHAPES[s.shape] + "</svg>" +
      "<span>" + s.label + "</span></span>"
    );
  }

  function escapeHtml(text) {
    return text.replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  /* A state as shape + word. A NEUTRAL week that is DEVELOPING shows both, since
     DEVELOPING is a flag on NEUTRAL rather than a state of its own. */
  function signalStateMarkup(state, developing) {
    var html = one(state);
    if (developing && state === "NEUTRAL") html += " " + one("DEVELOPING");
    return html;
  }

  /* The compact form for one-line summaries ("Where <stock> stands today"): the same shape and
     colour as signalStateMarkup, followed by a short factual descriptor in plain ink. */
  function summaryStateMarkup(state, developing, descriptor) {
    return '<span class="summary-state">' + signalStateMarkup(state, developing) + "</span>" +
      (descriptor ? ' <span class="summary-desc">' + escapeHtml(descriptor) + "</span>" : "");
  }

  window.SignalStyle = { signalStateMarkup: signalStateMarkup, summaryStateMarkup: summaryStateMarkup };

  /* Pages share data already fetched instead of fetching it twice: a script that loaded a
     system's reading publishes it here, and anything else on the page can read it. */
  var state = window.InvestIQState || (window.InvestIQState = {});
  window.InvestIQ = {
    publish: function (name, payload) {
      state[name] = payload;
      window.dispatchEvent(new CustomEvent("investiq:state", { detail: { name: name, payload: payload } }));
    },
  };
})();
