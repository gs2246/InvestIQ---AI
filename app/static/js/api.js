/* Shared fetch helper for data that can change after a write (watchlist, journal, holdings).
   Every GET uses cache "no-store" so a page never shows a stale copy after an add or delete.
   Every failure becomes an Error whose message can be shown to the user as-is; a 503 carries
   the server's "database isn't configured" message. */
(function () {
  "use strict";

  async function request(method, url, body) {
    var options = { method: method, cache: "no-store", headers: {} };
    if (body !== undefined) {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(body);
    }
    var res;
    try {
      res = await fetch(url, options);
    } catch (e) {
      throw new Error("The app's server could not be reached. Check that the InvestIQ window opened by start.bat is still running.");
    }
    var data = null;
    try { data = await res.json(); } catch (e) { /* not JSON */ }
    if (!res.ok) {
      var err = new Error((data && typeof data.detail === "string" && data.detail) || "The server answered with an error (" + res.status + ").");
      err.status = res.status;
      throw err;
    }
    return data;
  }

  function escapeHtml(text) {
    return String(text).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  /* Run a write while its button says what is happening ("Adding…" etc.), always restoring it. */
  async function withBusy(button, busyText, work) {
    var original = button.textContent;
    button.disabled = true;
    button.textContent = busyText;
    try {
      return await work();
    } finally {
      button.disabled = false;
      button.textContent = original;
    }
  }

  window.Api = {
    get: function (url) { return request("GET", url); },
    post: function (url, body) { return request("POST", url, body); },
    del: function (url) { return request("DELETE", url); },
    escapeHtml: escapeHtml,
    withBusy: withBusy,
  };
})();
