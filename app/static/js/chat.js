/* AI chat for one stock. Multi-turn but stateless on the server: the conversation lives
   only in this array, is sent with every question, and disappears when the page closes. */
(function () {
  "use strict";

  var root = document.getElementById("ai-chat");
  var form = document.getElementById("chat-form");
  if (!root || !form) return; // AI not configured: the page already says so
  var symbol = root.dataset.symbol;
  var log = document.getElementById("chat-log");
  var input = document.getElementById("chat-input");
  var send = document.getElementById("chat-send");
  var errorEl = document.getElementById("chat-error");
  var history = []; // [{role: "user" | "ai", text}]

  function addTurn(role, text) {
    var turn = document.createElement("div");
    turn.className = "chat-turn " + (role === "user" ? "chat-user" : "chat-ai");
    var who = document.createElement("span");
    who.className = "chat-who";
    who.textContent = role === "user" ? "You" : "AI";
    var body = document.createElement("p");
    body.className = "chat-text";
    body.textContent = text; // plain text only, never HTML
    turn.appendChild(who);
    turn.appendChild(body);
    log.appendChild(turn);
    return turn;
  }

  function showError(message) {
    errorEl.textContent = message || "";
    errorEl.hidden = !message;
  }

  form.addEventListener("submit", async function (event) {
    event.preventDefault();
    var question = input.value.trim();
    if (!question) {
      showError("Please type a question first.");
      return;
    }
    showError(null);
    addTurn("user", question);
    var pending = addTurn("ai", "Thinking…");
    pending.classList.add("chat-pending");
    input.value = "";
    input.disabled = true;
    send.disabled = true;
    send.textContent = "Asking…";
    try {
      var res = await fetch("/api/stocks/" + encodeURIComponent(symbol) + "/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: question, history: history }),
      });
      var data = await res.json();
      if (data && data.reply) {
        pending.querySelector(".chat-text").textContent = data.reply;
        pending.classList.remove("chat-pending");
        history.push({ role: "user", text: question });
        history.push({ role: "ai", text: data.reply });
      } else {
        pending.remove();
        showError((data && data.error) || "The AI did not answer. Please try again.");
      }
    } catch (err) {
      pending.remove();
      showError("The app's server could not be reached. Check that the InvestIQ window opened by start.bat is still running.");
    } finally {
      input.disabled = false;
      send.disabled = false;
      send.textContent = "Ask";
      input.focus();
    }
  });

  // Enter sends; Shift+Enter makes a new line.
  input.addEventListener("keydown", function (event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      form.requestSubmit();
    }
  });
})();
