/* The title cover shown while a page's data loads.
   It lifts when BOTH no request is in flight (each one held until its body has fully
   downloaded) AND no .skeleton placeholder is still visible.
   Stall detection: if requests have settled but skeletons remain (say a script failed),
   it lifts once the page has stopped changing for 2.5 s.
   Failsafe: it always lifts after 25 s. (The page also has an inline 35 s timer that works
   even if this file never loads, and a <noscript> rule for when JavaScript is off.)
   This file must load before the page's own scripts so it sees their requests. */
(function () {
  "use strict";

  var splash = document.getElementById("splash");
  if (!splash) return;

  var STALL_MS = 2500;
  var FAILSAFE_MS = 25000; // must stay shorter than the 35 s inline timer
  var started = Date.now();
  var lastChange = started;
  var inflight = 0;
  var domReady = false;
  var lifted = false;
  var originalFetch = window.fetch;

  function touch() { lastChange = Date.now(); }
  function settle() { inflight = Math.max(0, inflight - 1); touch(); }

  if (originalFetch) {
    window.fetch = function () {
      inflight += 1;
      touch();
      var request = originalFetch.apply(this, arguments);
      // Count the request as finished only once its body has fully arrived. A clone is read,
      // so the page's own code can still read the original response.
      request.then(function (response) {
        return response.clone().arrayBuffer().catch(function () {});
      }, function () {}).then(settle, settle);
      return request;
    };
  }

  function skeletonVisible() {
    var items = document.querySelectorAll(".skeleton");
    for (var i = 0; i < items.length; i++) {
      if (items[i].getClientRects().length > 0) return true; // hidden ones have no boxes
    }
    return false;
  }

  function lift() {
    if (lifted) return;
    lifted = true;
    clearInterval(timer);
    observer.disconnect();
    if (originalFetch) window.fetch = originalFetch;
    splash.classList.add("splash-lifting");
    setTimeout(function () { if (splash.parentNode) splash.parentNode.removeChild(splash); }, 350);
  }

  var observer = new MutationObserver(touch);
  observer.observe(document.documentElement, { subtree: true, childList: true, attributes: true, characterData: true });
  document.addEventListener("DOMContentLoaded", function () { domReady = true; touch(); });

  var timer = setInterval(function () {
    var now = Date.now();
    if (now - started > FAILSAFE_MS) { lift(); return; }
    if (!domReady || inflight > 0) return;
    if (!skeletonVisible() || now - lastChange > STALL_MS) lift();
  }, 100);
})();
