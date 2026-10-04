/* First-visit note on stock pages, pointing to the Screener. Shown until dismissed; the dismissal
   is remembered in localStorage. If storage is unavailable (private mode, blocked), the note is
   simply shown, and never causes an error. */
(function () {
  "use strict";

  var note = document.getElementById("orientation");
  var button = document.getElementById("orientation-dismiss");
  if (!note || !button) return;
  var KEY = "investiq.orientation.dismissed";

  function seen() {
    try { return window.localStorage.getItem(KEY) === "1"; } catch (e) { return false; }
  }
  if (!seen()) note.hidden = false;

  button.addEventListener("click", function () {
    note.hidden = true;
    try { window.localStorage.setItem(KEY, "1"); } catch (e) { /* storage unavailable: hide for now only */ }
  });
})();
