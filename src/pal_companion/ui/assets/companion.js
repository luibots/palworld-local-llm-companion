const form = document.querySelector("#askForm");
const question = document.querySelector("#question");
const askButton = document.querySelector("#askButton");
const includeLive = document.querySelector("#includeLive");
const allowWeb = document.querySelector("#allowWeb");
const webFilter = document.querySelector("#webFilter");
const webFilterText = document.querySelector("#webFilterText");
const autoRead = document.querySelector("#autoRead");
const voiceFilter = document.querySelector("#voiceFilter");
const voiceFilterText = document.querySelector("#voiceFilterText");
const voiceStatus = document.querySelector("#voiceStatus");
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
const readButton = document.querySelector("#readButton");
const stopVoiceButton = document.querySelector("#stopVoiceButton");
const markerSection = document.querySelector("#markerSection");
const markersRoot = document.querySelector("#markers");
const placeAllButton = document.querySelector("#placeAllButton");
const markerStatus = document.querySelector("#markerStatus");
const sourcesRoot = document.querySelector("#sources");
const sourceCount = document.querySelector("#sourceCount");
const history = JSON.parse(localStorage.getItem("pal-companion-history") || "[]");
const speechSupported = "speechSynthesis" in window && "SpeechSynthesisUtterance" in window;
const gameClient = new URLSearchParams(window.location.search).get("client") === "ue4ss";
const stopVoicePattern = /^(?:please\s+)?(?:stop|stop\s+(?:talking|speaking|voice)|be\s+quiet|silence|shut\s+up)(?:\s+to\s+me)?[.!]?$/i;
let currentAnswer = "";
let currentMarkers = [];

document.body.classList.toggle("game-client", gameClient);

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

function setVoiceState(speaking, message) {
  stopVoiceButton.disabled = !speechSupported || !speaking;
  voiceStatus.textContent = message;
}

function stopVoice(message = "VOICE STOPPED") {
  if (speechSupported) window.speechSynthesis.cancel();
  setVoiceState(false, message);
}

function spokenVersion(text) {
  return text
    .replace(/\[[^\]]+\]/g, "")
    .replace(/^\s*[-*]\s+/gm, "")
    .replace(/\n{2,}/g, ". ")
    .replace(/\n/g, ". ")
    .replace(/\s+/g, " ")
    .trim();
}

function preferredVoice() {
  const voices = window.speechSynthesis.getVoices();
  return (
    voices.find((voice) => voice.lang.startsWith("en") && voice.localService) ||
    voices.find((voice) => voice.lang.startsWith("en")) ||
    voices[0]
  );
}

function readAnswer() {
  if (!speechSupported || !currentAnswer) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(spokenVersion(currentAnswer));
  const voice = preferredVoice();
  if (voice) utterance.voice = voice;
  utterance.rate = 0.95;
  utterance.pitch = 1.02;
  utterance.onstart = () => setVoiceState(true, "READING ANSWER");
  utterance.onend = () => setVoiceState(false, "VOICE READY");
  utterance.onerror = () => setVoiceState(false, "VOICE ERROR");
  window.speechSynthesis.speak(utterance);
}

function markerCommand(markers) {
  const payload = markers
    .map((marker) => `${Number(marker.x)},${Number(marker.y)}`)
    .join(";");
  window.location.hash = `palmarkers=${Date.now()};${payload}`;
  markerStatus.textContent =
    `${markers.length} MARKER${markers.length === 1 ? "" : "S"} REQUESTED IN GAME`;
}

async function copyMarker(marker) {
  const text = `${marker.x}, ${marker.y}`;
  try {
    await navigator.clipboard.writeText(text);
    markerStatus.textContent = `COPIED ${text}`;
  } catch {
    markerStatus.textContent = `COORDINATES ${text}`;
  }
}

function activateMarkers(markers) {
  if (!markers.length) return;
  if (gameClient) {
    markerCommand(markers);
    return;
  }
  if (markers.length === 1) {
    copyMarker(markers[0]);
    return;
  }
  navigator.clipboard
    .writeText(markers.map((marker) => `${marker.label}: ${marker.x}, ${marker.y}`).join("\n"))
    .then(() => {
      markerStatus.textContent = `${markers.length} MARKERS COPIED`;
    })
    .catch(() => {
      markerStatus.textContent = "COPY UNAVAILABLE";
    });
}

function renderMarkers(markers) {
  currentMarkers = markers;
  markersRoot.replaceChildren();
  markerSection.hidden = markers.length === 0;
  markerStatus.textContent = "";
  placeAllButton.textContent = gameClient ? "PLACE ALL" : "COPY ALL";

  markers.forEach((marker) => {
    const row = document.createElement("div");
    row.className = "marker";

    const label = document.createElement("span");
    label.className = "marker-label";
    label.textContent = marker.label;
    label.title = marker.label;

    const coordinates = document.createElement("span");
    coordinates.className = "marker-coordinates";
    coordinates.textContent = `${marker.x}, ${marker.y}`;

    const action = document.createElement("button");
    action.className = "tool-button";
    action.type = "button";
    action.textContent = gameClient ? "PLACE" : "COPY";
    action.addEventListener("click", () => activateMarkers([marker]));

    row.append(label, coordinates, action);
    markersRoot.append(row);
  });
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
    indexCount.textContent =
      `${data.indexed_documents || 0} SOURCES / ${data.cached_answers || 0} CACHED`;
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
  if (stopVoicePattern.test(text)) {
    stopVoice();
    question.value = "";
    question.focus();
    return;
  }

  stopVoice("VOICE READY");
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
    currentAnswer = data.text;
    confidence.className = `confidence ${data.confidence}`;
    confidence.textContent =
      `${data.confidence.toUpperCase()} CONFIDENCE${data.cached ? " / CACHED" : ""}`;
    renderMarkers(data.coordinates || []);
    renderSources(data.sources || []);
    remember(text);
    show(answerState);
    if (autoRead.checked) readAnswer();
  } catch (error) {
    errorText.textContent = error instanceof Error ? error.message : String(error);
    show(errorState);
  } finally {
    askButton.disabled = false;
  }
});

autoRead.checked = localStorage.getItem("pal-companion-auto-read") !== "false";
autoRead.addEventListener("change", () => {
  localStorage.setItem("pal-companion-auto-read", String(autoRead.checked));
  if (!autoRead.checked) stopVoice("AUTO READ OFF");
  else setVoiceState(false, "VOICE READY");
});
readButton.addEventListener("click", readAnswer);
stopVoiceButton.addEventListener("click", () => stopVoice());
placeAllButton.addEventListener("click", () => activateMarkers(currentMarkers));

if (!speechSupported) {
  autoRead.checked = false;
  autoRead.disabled = true;
  readButton.disabled = true;
  stopVoiceButton.disabled = true;
  voiceFilter.title = "Speech is unavailable in this browser";
  voiceFilterText.textContent = "VOICE UNAVAILABLE";
  voiceStatus.textContent = "VOICE UNAVAILABLE";
}

renderHistory();
checkHealth();
window.setInterval(checkHealth, 15000);
