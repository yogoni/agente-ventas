const form = document.querySelector("#chat-form");
const input = document.querySelector("#message");
const sendButton = document.querySelector("#send");
const messages = document.querySelector("#messages");
const status = document.querySelector("#status");
const newChatButton = document.querySelector("#new-chat");
let sessionId = null;
let busy = false;

function addMessage(text, kind) {
  const bubble = document.createElement("div");
  bubble.className = `bubble ${kind}`;
  bubble.textContent = text;
  messages.append(bubble);
  messages.scrollTop = messages.scrollHeight;
  return bubble;
}

function feedbackButton(symbol, score, label) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "feedback-btn";
  button.textContent = symbol;
  button.setAttribute("aria-label", label);
  button.addEventListener("click", () => submitFeedback(button, score));
  return button;
}

function addFeedback(bubble, runId) {
  if (!runId) return;
  const row = document.createElement("div");
  row.className = "feedback";
  row.dataset.runId = runId;

  const note = document.createElement("span");
  note.className = "feedback-note";
  note.textContent = "¿Te ha servido?";

  row.append(note, feedbackButton("👍", 1, "Respuesta útil"), feedbackButton("👎", 0, "Respuesta poco útil"));
  bubble.after(row);
  messages.scrollTop = messages.scrollHeight;
}

async function submitFeedback(button, score) {
  const row = button.closest(".feedback");
  if (!row || row.dataset.sent) return;
  const buttons = row.querySelectorAll(".feedback-btn");
  buttons.forEach((item) => (item.disabled = true));

  try {
    const response = await fetch("/api/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        run_id: row.dataset.runId,
        score,
        comment: score === 1 ? "thumbs_up" : "thumbs_down",
      }),
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || "No se pudo registrar el feedback.");
    }
    row.dataset.sent = "1";
    button.classList.add("selected");
    row.querySelector(".feedback-note").textContent = "¡Gracias por el feedback!";
  } catch (error) {
    buttons.forEach((item) => (item.disabled = false));
    status.textContent = error.message;
  }
}

async function sendMessage(text) {
  const message = text.trim();
  if (!message || busy) return;
  busy = true;
  sendButton.disabled = true;
  status.textContent = "";
  messages.querySelector(".welcome")?.remove();
  addMessage(message, "user");
  const pending = addMessage("Consultando las ventas…", "assistant pending");
  input.value = "";
  input.style.height = "auto";

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, session_id: sessionId }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "No se pudo obtener una respuesta.");
    sessionId = result.session_id;
    pending.classList.remove("pending");
    pending.textContent = result.reply;
    addFeedback(pending, result.run_id);
  } catch (error) {
    pending.remove();
    status.textContent = error.message;
  } finally {
    busy = false;
    sendButton.disabled = false;
    input.focus();
    messages.scrollTop = messages.scrollHeight;
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  sendMessage(input.value);
});

input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

input.addEventListener("input", () => {
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 150)}px`;
});

document.querySelectorAll("[data-prompt]").forEach((button) => {
  button.addEventListener("click", () => sendMessage(button.dataset.prompt));
});

newChatButton.addEventListener("click", async () => {
  if (busy) return;
  const previousSession = sessionId;
  sessionId = null;
  messages.replaceChildren();
  status.textContent = "Nueva conversación iniciada.";
  input.focus();
  if (previousSession) {
    try {
      await fetch("/api/reset", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: previousSession }),
      });
    } catch (_) {
      // A reset failure does not affect the new conversation.
    }
  }
});
