const form = document.querySelector("#askForm");
const question = document.querySelector("#question");
const askButton = document.querySelector("#askButton");
const includeLive = document.querySelector("#includeLive");
const allowWeb = document.querySelector("#allowWeb");
const webFilter = document.querySelector("#webFilter");
const webFilterText = document.querySelector("#webFilterText");
const status = document.querySelector("#status");
const statusText = document.querySelector("#statusText");
const indexCount = document.querySelector("#indexCount");
const historyRoot = document.querySelector("#history");
const emptyState = document.querySelector("#emptyState");
const loadingState = document.querySelector("#loadingState");
const answerState = document.querySelector("#answerState");
const errorState = document.querySelector("#errorState");
const errorText = document.querySelector("#errorText");
const answerText = document.querySelector("#answerText");
const confidence = document.querySelector("#confidence");
const sourcesRoot = document.querySelector("#sources");
const sourceCount = document.querySelector("#sourceCount");
const history = JSON.parse(localStorage.getItem("pal-companion-history") || "[]");

function show(target) {
  [emptyState, loadingState, answerState, errorState].forEach((item) => {
    item.hidden = item !== target;
  });
}

function renderHistory() {
  historyRoot.replaceChildren();
  history.slice(0, 8).forEach((text) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = text;
    button.title = text;
    button.addEventListener("click", () => {
      question.value = text;
      question.focus();
    });
    historyRoot.append(button);
  });
}

function remember(text) {
  const existing = history.indexOf(text);
  if (existing >= 0) history.splice(existing, 1);
  history.unshift(text);
  history.splice(8);
  localStorage.setItem("pal-companion-history", JSON.stringify(history));
  renderHistory();
}

function renderSources(sources) {
  sourcesRoot.replaceChildren();
  sourceCount.textContent = String(sources.length);
  sources.forEach((source, index) => {
    const row = document.createElement(source.url ? "a" : "div");
    row.className = "source";
    if (source.url) {
      row.href = source.url;
      row.target = "_blank";
      row.rel = "noreferrer";
    }

    const number = document.createElement("span");
    number.className = "source-index";
    number.textContent = String(index + 1).padStart(2, "0");

    const title = document.createElement("span");
    title.textContent = source.title;

    const kind = document.createElement("span");
    kind.className = "source-kind";
    kind.textContent = source.kind.toUpperCase();
    row.append(number, title, kind);
    sourcesRoot.append(row);
  });
}

async function checkHealth() {
  try {
    const response = await fetch("/health", { cache: "no-store" });
    const data = await response.json();
    const ready = response.ok && data.ollama;
    status.classList.toggle("offline", !ready);
    statusText.textContent = ready ? "OLLAMA READY" : "OLLAMA OFFLINE";
    indexCount.textContent = `${data.indexed_documents || 0} SOURCES INDEXED`;
    const webConfigured = Boolean(data.web_search_configured);
    allowWeb.disabled = !webConfigured;
    if (!webConfigured) allowWeb.checked = false;
    webFilterText.textContent = webConfigured ? "WEB GUIDES" : "WEB NOT CONFIGURED";
    webFilter.title = webConfigured
      ? "Search current Palworld web sources"
      : "Set BRAVE_SEARCH_API_KEY in the local .env file";
  } catch {
    status.classList.add("offline");
    statusText.textContent = "COMPANION OFFLINE";
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = question.value.trim();
  if (!text) return;

  askButton.disabled = true;
  show(loadingState);
  try {
    const response = await fetch("/ask", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: text,
        allow_web: allowWeb.checked,
        include_live: includeLive.checked,
      }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);

    answerText.textContent = data.text;
    confidence.className = `confidence ${data.confidence}`;
    confidence.textContent = `${data.confidence.toUpperCase()} CONFIDENCE`;
    renderSources(data.sources || []);
    remember(text);
    show(answerState);
  } catch (error) {
    errorText.textContent = error instanceof Error ? error.message : String(error);
    show(errorState);
  } finally {
    askButton.disabled = false;
  }
});

renderHistory();
checkHealth();
window.setInterval(checkHealth, 15000);
