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
const micFilter = document.querySelector("#micFilter");
const micConfirm = document.querySelector("#micConfirm");
const micFilterText = document.querySelector("#micFilterText");
const voiceSelect = document.querySelector("#voiceSelect");
const playerLevel = document.querySelector("#playerLevel");
const targetX = document.querySelector("#targetX");
const targetY = document.querySelector("#targetY");
const placeTargetButton = document.querySelector("#placeTargetButton");
const targetStatus = document.querySelector("#targetStatus");
const voiceStatus = document.querySelector("#voiceStatus");
const status = document.querySelector("#status");
const statusText = document.querySelector("#statusText");
const indexCount = document.querySelector("#indexCount");
const vendorButton = document.querySelector("#vendorButton");
const storageButton = document.querySelector("#storageButton");
const vendorState = document.querySelector("#vendorState");
const vendorList = document.querySelector("#vendorList");
const vendorStatus = document.querySelector("#vendorStatus");
const vendorProximity = document.querySelector("#vendorProximity");
const closeVendorsButton = document.querySelector("#closeVendorsButton");
const rareTargetList = document.querySelector("#rareTargetList");
const storageState = document.querySelector("#storageState");
const storageMode = document.querySelector("#storageMode");
const closeStorageButton = document.querySelector("#closeStorageButton");
const scanStorageButton = document.querySelector("#scanStorageButton");
const planStorageButton = document.querySelector("#planStorageButton");
const applyStorageButton = document.querySelector("#applyStorageButton");
const storageChestCount = document.querySelector("#storageChestCount");
const storageStackCount = document.querySelector("#storageStackCount");
const storageMoveCount = document.querySelector("#storageMoveCount");
const storageChestList = document.querySelector("#storageChestList");
const storagePlanList = document.querySelector("#storagePlanList");
const storageStatus = document.querySelector("#storageStatus");
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
const markerPrompt = document.querySelector("#markerPrompt");
const markerPromptText = document.querySelector("#markerPromptText");
const confirmMarkersButton = document.querySelector("#confirmMarkersButton");
const declineMarkersButton = document.querySelector("#declineMarkersButton");
const markerStatus = document.querySelector("#markerStatus");
const sourcesRoot = document.querySelector("#sources");
const sourceCount = document.querySelector("#sourceCount");
const history = JSON.parse(localStorage.getItem("pal-companion-history") || "[]");
const queryParams = new URLSearchParams(window.location.search);
const gameClient = queryParams.get("client") === "ue4ss";
const playerName = queryParams.get("player")?.trim() || null;
const stopVoicePattern = /^(?:please\s+)?(?:stop|stop\s+(?:talking|speaking|voice)|be\s+quiet|silence|shut\s+up)(?:\s+to\s+me)?[.!]?$/i;
const confirmMarkerPattern = /^(?:yes|yeah|yep|sure|okay|ok|do it|place (?:it|them)|put (?:it|them)(?: on (?:the|my) map)?|mark (?:it|them))[\s.!]*$/i;
const declineMarkerPattern = /^(?:no|nope|not now|cancel|don't|do not)[\s.!]*$/i;
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
const markerIcons = {
  pin: { type: 0, glyph: "+", label: "Pinpoint" },
  star: { type: 1, glyph: "*", label: "Star" },
  box: { type: 2, glyph: "B", label: "Chest" },
  resource: { type: 3, glyph: "R", label: "Resource" },
  pal: { type: 4, glyph: "P", label: "Pal" },
  food: { type: 5, glyph: "F", label: "Food" },
  boss: { type: 6, glyph: "!", label: "Boss" },
  base: { type: 7, glyph: "H", label: "Base" },
  fruit: { type: 8, glyph: "A", label: "Fruit" },
  dungeon: { type: 9, glyph: "D", label: "Dungeon" },
  egg: { type: 10, glyph: "E", label: "Egg" },
  person: { type: 11, glyph: "N", label: "Person" },
  book: { type: 12, glyph: "K", label: "Book" },
  flower: { type: 13, glyph: "L", label: "Flower" },
};
let currentAnswer = "";
let currentSpokenSummary = "";
let currentMarkers = [];
let pendingMarkers = [];
let currentAudio = null;
let currentAudioUrl = null;
let voiceAbortController = null;
let neuralVoiceReady = false;
let markerRecognition = null;
let markerListening = false;
let markerListenAbortController = null;
let localSpeechReady = false;
let vendorsLoaded = false;
let currentStorageSnapshot = null;
let currentStoragePlan = null;
let storageApplyArmed = false;
const markerChime = new Audio("/assets/marker-chime.mp3");
markerChime.preload = "auto";

document.body.classList.toggle("game-client", gameClient);

function historyAppearance(text) {
  const value = text.toLowerCase();
  if (/(foxicle|ice|frost|snow|chillet|pengullet)/.test(value)) {
    return { kind: "ice", glyph: "*", label: "Ice" };
  }
  if (/(fire|flame|blazamut|jormuntide ignis|kindling)/.test(value)) {
    return { kind: "fire", glyph: "^", label: "Fire" };
  }
  if (/(coal|ore|stone|sulfur|quartz|paldium|ingot|oil|wood|fiber)/.test(value)) {
    return { kind: "resource", glyph: "◆", label: "Resource" };
  }
  if (/(where|location|coordinate|map|dungeon|cave)/.test(value)) {
    return { kind: "location", glyph: "+", label: "Location" };
  }
  if (/(pal|breed|capture|drop|partner|boss)/.test(value)) {
    return { kind: "pal", glyph: "P", label: "Pal" };
  }
  if (/(best|strategy|build|armor|weapon|base)/.test(value)) {
    return { kind: "strategy", glyph: "!", label: "Strategy" };
  }
  return { kind: "general", glyph: "?", label: "General" };
}

function show(target) {
  [emptyState, loadingState, vendorState, storageState, answerState, errorState].forEach((item) => {
    item.hidden = item !== target;
  });
}

function vendorMarker(vendor) {
  return {
    label: vendor.name,
    x: vendor.x,
    y: vendor.y,
    icon: "person",
  };
}

function vendorLevelStatus(vendor) {
  const level = Number(playerLevel.value);
  if (!level || !vendor.level) return `LV ${vendor.level || "?"}`;
  if (vendor.level > level) return `OVER LEVEL / LV ${vendor.level}`;
  return `LEVEL MATCH / LV ${vendor.level}`;
}

async function shareVendor(vendor, button) {
  button.disabled = true;
  vendorStatus.textContent = `QUEUEING ${vendor.name.toUpperCase()} FOR DISCORD`;
  try {
    const response = await fetch("/guild/share-vendor", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        vendor_id: vendor.vendor_id,
        player_name: playerName,
      }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || `Share failed (${response.status})`);
    vendorStatus.textContent = "QUEUED FOR THE GUILD DISCORD";
    button.textContent = "QUEUED";
  } catch (error) {
    vendorStatus.textContent =
      error instanceof Error ? error.message.toUpperCase() : "DISCORD QUEUE FAILED";
    button.disabled = false;
  }
}

function renderVendors(vendors) {
  vendorList.replaceChildren();
  const hasDistance = vendors.some((vendor) => vendor.distance !== null);
  vendorProximity.textContent = hasDistance ? "SORTED FROM YOUR LIVE POSITION" : "LIVE POSITION UNAVAILABLE";

  vendors.forEach((vendor, index) => {
    const card = document.createElement("article");
    card.className = "vendor-card";
    if (index === 0 && hasDistance) card.classList.add("nearest");
    if (vendor.premium_stock) card.classList.add("premium");

    const identity = document.createElement("div");
    identity.className = "vendor-identity";

    const icon = document.createElement("span");
    icon.className = "vendor-icon";
    icon.textContent = "N";
    icon.setAttribute("aria-hidden", "true");

    const titleGroup = document.createElement("div");
    const title = document.createElement("h3");
    title.textContent = vendor.name;
    const destination = document.createElement("p");
    destination.textContent = vendor.fast_travel;
    titleGroup.append(title, destination);
    identity.append(icon, titleGroup);

    const badges = document.createElement("div");
    badges.className = "vendor-badges";
    const levelBadge = document.createElement("span");
    levelBadge.className =
      Number(playerLevel.value) && vendor.level > Number(playerLevel.value)
        ? "vendor-badge danger"
        : "vendor-badge level";
    levelBadge.textContent = vendorLevelStatus(vendor);
    const reliabilityBadge = document.createElement("span");
    reliabilityBadge.className = "vendor-badge verified";
    reliabilityBadge.textContent = vendor.reliability.toUpperCase();
    badges.append(levelBadge, reliabilityBadge);
    if (vendor.premium_stock) {
      const premiumBadge = document.createElement("span");
      premiumBadge.className = "vendor-badge premium";
      premiumBadge.textContent = "BEST VERIFIED STOCK";
      badges.append(premiumBadge);
    }
    if (vendor.underground) {
      const caveBadge = document.createElement("span");
      caveBadge.className = "vendor-badge cave";
      caveBadge.textContent = "UNDERGROUND";
      badges.append(caveBadge);
    }

    const route = document.createElement("p");
    route.className = "vendor-route";
    route.textContent = vendor.route;

    const stock = document.createElement("p");
    stock.className = "vendor-stock";
    stock.textContent =
      `${vendor.stock_summary} Stock levels ${vendor.stock_level_min}-${vendor.stock_level_max}. ` +
      "Final cost scales with the rolled Pal level.";

    const stockHighlights = document.createElement("div");
    stockHighlights.className = "vendor-stock-highlights";
    vendor.stock_highlights.forEach((pal) => {
      const highlight = document.createElement("div");
      highlight.className = "vendor-stock-pal";

      const palName = document.createElement("strong");
      palName.textContent = pal.name;
      const specialty = document.createElement("span");
      specialty.textContent = pal.specialty;
      const price = document.createElement("b");
      price.textContent = `${pal.base_price.toLocaleString()} BASE`;

      highlight.append(palName, specialty, price);
      stockHighlights.append(highlight);
    });

    const coordinate = document.createElement("span");
    coordinate.className = "vendor-coordinate";
    coordinate.textContent = `${vendor.x}, ${vendor.y}`;

    const distance = document.createElement("span");
    distance.className = "vendor-distance";
    distance.textContent =
      vendor.distance === null
        ? "DISTANCE UNKNOWN"
        : `${Math.round(vendor.distance)} MAP UNITS AWAY${index === 0 ? " / NEAREST" : ""}`;

    const actions = document.createElement("div");
    actions.className = "vendor-actions";
    const mark = document.createElement("button");
    mark.className = "vendor-action primary";
    mark.type = "button";
    mark.textContent = gameClient ? "MARK ROUTE" : "COPY COORDS";
    mark.addEventListener("click", () => activateMarkers([vendorMarker(vendor)]));
    const share = document.createElement("button");
    share.className = "vendor-action";
    share.type = "button";
    share.textContent = "GUILD";
    share.addEventListener("click", () => shareVendor(vendor, share));
    actions.append(mark, share);

    const meta = document.createElement("div");
    meta.className = "vendor-meta";
    meta.append(coordinate, distance, actions);

    card.append(identity, badges, route, stock, stockHighlights, meta);
    vendorList.append(card);
  });
}

function renderRareTargets(targets) {
  rareTargetList.replaceChildren();
  targets.forEach((target) => {
    const card = document.createElement("article");
    card.className = "rare-target";

    const heading = document.createElement("div");
    heading.className = "rare-target-heading";
    const label = document.createElement("span");
    label.textContent = "RARE HUNT";
    const name = document.createElement("strong");
    name.textContent = target.name;
    const value = document.createElement("b");
    value.textContent = `${target.base_price.toLocaleString()} BASE`;
    heading.append(label, name, value);

    const details = document.createElement("p");
    details.textContent =
      `LV ${target.level_min}-${target.level_max} / ${target.specialty}. ${target.vendor_note}`;

    const actions = document.createElement("div");
    actions.className = "rare-target-actions";
    const locations = document.createElement("span");
    locations.textContent = target.locations
      .map((marker) => `${marker.x}, ${marker.y}`)
      .join(" / ");
    const mark = document.createElement("button");
    mark.className = "vendor-action primary";
    mark.type = "button";
    mark.textContent = gameClient ? "MARK HUNT" : "COPY COORDS";
    mark.addEventListener("click", () => activateMarkers(target.locations));
    actions.append(locations, mark);

    card.append(heading, details, actions);
    rareTargetList.append(card);
  });
}

async function openVendorDirectory() {
  stopMarkerListening();
  stopVoice("VOICE READY");
  show(vendorState);
  vendorStatus.textContent = vendorsLoaded ? "" : "LOADING VERIFIED VENDORS";
  try {
    const params = new URLSearchParams();
    if (playerName) params.set("player_name", playerName);
    const [vendorResponse, targetResponse] = await Promise.all([
      fetch(`/vendors?${params}`, {
        credentials: "same-origin",
        cache: "no-store",
      }),
      fetch("/rare-targets", {
        credentials: "same-origin",
        cache: "no-store",
      }),
    ]);
    const [vendors, targets] = await Promise.all([
      vendorResponse.json(),
      targetResponse.json(),
    ]);
    if (!vendorResponse.ok) {
      throw new Error(vendors.detail || `Vendor lookup failed (${vendorResponse.status})`);
    }
    if (!targetResponse.ok) {
      throw new Error(targets.detail || `Rare target lookup failed (${targetResponse.status})`);
    }
    renderRareTargets(targets);
    renderVendors(vendors);
    vendorsLoaded = true;
    vendorStatus.textContent = "";
  } catch (error) {
    vendorStatus.textContent =
      error instanceof Error ? error.message.toUpperCase() : "VENDOR DIRECTORY UNAVAILABLE";
  }
}

window.palCompanionOpenVendors = openVendorDirectory;

function resetStorageApply() {
  storageApplyArmed = false;
  applyStorageButton.textContent = currentStoragePlan?.can_execute
    ? "ARM APPLY"
    : "REVIEW FIRST";
}

function renderStorageChests(containers) {
  storageChestList.replaceChildren();
  storageChestCount.textContent = String(containers.length);
  const stackCount = containers.reduce((total, container) => total + container.items.length, 0);
  storageStackCount.textContent = String(stackCount);

  if (!containers.length) {
    const empty = document.createElement("div");
    empty.className = "storage-empty";
    empty.textContent = "NO PLAYER-OWNED LOADED CHESTS";
    storageChestList.append(empty);
    return;
  }

  containers.forEach((container, index) => {
    const row = document.createElement("div");
    row.className = `storage-chest${container.label ? " labeled" : ""}`;
    const identity = document.createElement("div");
    const name = document.createElement("strong");
    name.textContent = container.label || `UNLABELED CHEST ${index + 1}`;
    const role = document.createElement("span");
    role.textContent = container.label ? "ORGANIZER ENABLED" : "IGNORED";
    identity.append(name, document.createElement("br"), role);
    const count = document.createElement("span");
    count.textContent = `${container.items.length} STACK${container.items.length === 1 ? "" : "S"}`;
    row.append(identity, count);
    storageChestList.append(row);
  });
}

function renderStoragePlan(plan) {
  currentStoragePlan = plan;
  storagePlanList.replaceChildren();
  storageMoveCount.textContent = String(plan.moves.length);
  storageMode.textContent =
    plan.planner === "local-llm" ? "LOCAL AI PLAN" : "LABEL RULE PLAN";
  plan.moves.forEach((move) => {
    const row = document.createElement("div");
    row.className = `storage-move ${move.confidence}`;
    row.title = move.reason;
    const item = document.createElement("div");
    const name = document.createElement("strong");
    name.textContent = move.display_name;
    const count = document.createElement("span");
    count.textContent = `${move.count.toLocaleString()} / SLOT ${move.source_slot + 1}`;
    item.append(name, document.createElement("br"), count);
    const arrow = document.createElement("span");
    arrow.className = "storage-arrow";
    arrow.textContent = ">";
    const target = document.createElement("strong");
    target.textContent = move.target_label;
    row.append(item, arrow, target);
    storagePlanList.append(row);
  });
  if (!plan.moves.length) {
    const empty = document.createElement("div");
    empty.className = "storage-empty";
    empty.textContent = "NO STACK MOVES REQUIRED";
    storagePlanList.append(empty);
  }

  planStorageButton.disabled = !currentStorageSnapshot;
  applyStorageButton.disabled = !gameClient || !plan.can_execute;
  resetStorageApply();
  const warnings = [...(plan.warnings || [])];
  if (plan.unmapped_items?.length) {
    warnings.push(`${plan.unmapped_items.length} ITEM TYPE(S) LEFT IN PLACE`);
  }
  storageStatus.textContent = [plan.summary, ...warnings].join(" / ").toUpperCase();
}

async function buildStoragePlan() {
  if (!currentStorageSnapshot) return;
  planStorageButton.disabled = true;
  applyStorageButton.disabled = true;
  storageMode.textContent = "LOCAL AI THINKING";
  storageStatus.textContent = "BUILDING VALIDATED MOVE PLAN";
  try {
    const response = await fetch("/storage/plan", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(currentStorageSnapshot),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Storage plan failed (${response.status})`);
    }
    renderStoragePlan(data);
  } catch (error) {
    currentStoragePlan = null;
    storageMode.textContent = "PLAN FAILED";
    storageStatus.textContent =
      error instanceof Error ? error.message.toUpperCase() : "STORAGE PLAN UNAVAILABLE";
    planStorageButton.disabled = false;
  }
}

function requestStorageScan() {
  show(storageState);
  currentStorageSnapshot = null;
  currentStoragePlan = null;
  resetStorageApply();
  storageMoveCount.textContent = "0";
  storagePlanList.replaceChildren();
  planStorageButton.disabled = true;
  applyStorageButton.disabled = true;
  if (!gameClient) {
    storageMode.textContent = "IN-GAME CLIENT REQUIRED";
    storageStatus.textContent = "OPEN STORAGE ROUTER WITH F4 IN PALWORLD";
    return;
  }
  storageMode.textContent = "SCANNING LOADED CHESTS";
  storageStatus.textContent = "READ-ONLY CLIENT SCAN RUNNING";
  window.location.hash = `palstorage=${Date.now()};scan`;
}

function openStorageOrganizer() {
  stopMarkerListening();
  stopVoice("VOICE READY");
  show(storageState);
  if (!currentStorageSnapshot) requestStorageScan();
}

function storageExecutionCommand(moves) {
  const groups = new Map();
  moves.slice(0, 32).forEach((move) => {
    if (!groups.has(move.target_container_id)) groups.set(move.target_container_id, []);
    groups
      .get(move.target_container_id)
      .push(`${move.source_container_id},${move.source_slot},${move.count}`);
  });
  return [...groups.entries()]
    .map(([target, sources]) => `${target}~${sources.join("~")}`)
    .join(";");
}

function applyStoragePlan() {
  if (!currentStoragePlan?.can_execute || !gameClient) return;
  if (!storageApplyArmed) {
    storageApplyArmed = true;
    applyStorageButton.textContent = `CONFIRM ${Math.min(32, currentStoragePlan.moves.length)} MOVES`;
    storageStatus.textContent = "REVIEW THE MOVE LIST, THEN CONFIRM APPLY";
    return;
  }
  const payload = storageExecutionCommand(currentStoragePlan.moves);
  if (!payload) return;
  applyStorageButton.disabled = true;
  storageMode.textContent = "SUBMITTING TO PALWORLD";
  storageStatus.textContent = "SOURCE STACKS ARE BEING REVALIDATED";
  window.location.hash = `palstorage=${Date.now()};execute;${payload}`;
}

window.palCompanionStorageSnapshot = (snapshot) => {
  if (!snapshot || !Array.isArray(snapshot.containers)) {
    window.palCompanionStorageError("Malformed storage snapshot.");
    return;
  }
  currentStorageSnapshot = snapshot;
  renderStorageChests(snapshot.containers);
  const labeled = snapshot.containers.filter((container) => container.label).length;
  const excluded = Math.max(0, Number(snapshot.excluded_container_count) || 0);
  storageMode.textContent = `${labeled} LABELED / ${snapshot.containers.length} YOURS`;
  storageStatus.textContent = labeled
    ? `CHEST SNAPSHOT READY / ${excluded} OTHER-PLAYER CHEST${excluded === 1 ? "" : "S"} EXCLUDED`
    : `NAME YOUR OWN CHESTS IN PALWORLD, THEN SCAN AGAIN / ${excluded} OTHER-PLAYER CHEST${excluded === 1 ? "" : "S"} EXCLUDED`;
  planStorageButton.disabled = !labeled;
  if (labeled) buildStoragePlan();
};

window.palCompanionStorageSubmitted = (submitted, rejected) => {
  const accepted = Math.max(0, Number(submitted) || 0);
  const denied = Math.max(0, Number(rejected) || 0);
  storageMode.textContent = "PALWORLD REQUEST SENT";
  storageStatus.textContent =
    `${accepted} MOVE${accepted === 1 ? "" : "S"} SUBMITTED` +
    (denied ? ` / ${denied} REJECTED DURING REVALIDATION` : "");
  window.setTimeout(requestStorageScan, 1400);
};

window.palCompanionStorageError = (message) => {
  storageMode.textContent = "STORAGE BRIDGE ERROR";
  storageStatus.textContent = String(message || "Storage bridge unavailable").toUpperCase();
  scanStorageButton.disabled = false;
};

function renderHistory() {
  historyRoot.replaceChildren();
  history.slice(0, 8).forEach((text) => {
    const button = document.createElement("button");
    const appearance = historyAppearance(text);
    button.type = "button";
    button.title = text;

    const icon = document.createElement("span");
    icon.className = `history-icon ${appearance.kind}`;
    icon.textContent = appearance.glyph;
    icon.title = appearance.label;
    icon.setAttribute("aria-hidden", "true");

    const label = document.createElement("span");
    label.className = "history-text";
    label.textContent = text;

    button.addEventListener("click", () => {
      question.value = text;
      question.focus();
    });
    button.append(icon, label);
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
  stopVoiceButton.disabled = !speaking;
  voiceStatus.textContent = message;
}

function stopVoice(message = "VOICE STOPPED") {
  if (voiceAbortController) {
    voiceAbortController.abort();
    voiceAbortController = null;
  }
  if (currentAudio) {
    currentAudio.pause();
    currentAudio.currentTime = 0;
    currentAudio = null;
  }
  if (currentAudioUrl) {
    URL.revokeObjectURL(currentAudioUrl);
    currentAudioUrl = null;
  }
  setVoiceState(false, message);
}

function stopMarkerListening() {
  if (markerRecognition && markerListening) {
    markerRecognition.abort();
  }
  if (markerListenAbortController) {
    markerListenAbortController.abort();
    markerListenAbortController = null;
  }
  markerListening = false;
  micFilterText.textContent = micConfirm.checked ? "MIC CONFIRM" : "MIC OFF";
}

function finishSpokenMarkerReply(transcript) {
  if (confirmMarkerPattern.test(transcript)) {
    finishMarkerPrompt(true);
    return;
  }
  if (declineMarkerPattern.test(transcript)) {
    finishMarkerPrompt(false);
    return;
  }
  setMarkerStatus(`HEARD "${transcript.toUpperCase()}": SAY YES OR NO`);
}

function createMarkerRecognition() {
  if (!SpeechRecognition || markerRecognition) return markerRecognition;
  markerRecognition = new SpeechRecognition();
  markerRecognition.continuous = false;
  markerRecognition.interimResults = false;
  markerRecognition.lang = "en-US";
  markerRecognition.addEventListener("start", () => {
    markerListening = true;
    micFilterText.textContent = "MIC LISTENING";
    setMarkerStatus("LISTENING FOR YES OR NO");
  });
  markerRecognition.addEventListener("result", (event) => {
    const transcript = event.results?.[0]?.[0]?.transcript?.trim() || "";
    if (transcript) finishSpokenMarkerReply(transcript);
  });
  markerRecognition.addEventListener("error", (event) => {
    if (event.error === "not-allowed" || event.error === "service-not-allowed") {
      micConfirm.checked = false;
      localStorage.setItem("pal-companion-mic-confirm", "false");
      setMarkerStatus("MICROPHONE PERMISSION REQUIRED");
    } else if (event.error !== "aborted" && event.error !== "no-speech") {
      setMarkerStatus("MIC CONFIRMATION UNAVAILABLE");
    }
  });
  markerRecognition.addEventListener("end", () => {
    markerListening = false;
    micFilterText.textContent = micConfirm.checked ? "MIC CONFIRM" : "MIC OFF";
  });
  return markerRecognition;
}

async function listenForLocalMarkerReply() {
  markerListening = true;
  const controller = new AbortController();
  markerListenAbortController = controller;
  micFilterText.textContent = "MIC LISTENING";
  setMarkerStatus("LISTENING FOR YES OR NO");

  try {
    const response = await fetch("/listen-confirmation", {
      method: "POST",
      credentials: "same-origin",
      signal: controller.signal,
    });
    if (controller.signal.aborted) return;
    markerListening = false;
    micFilterText.textContent = "MIC THINKING";
    setMarkerStatus("TRANSCRIBING LOCALLY");
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Transcription failed (${response.status})`);
    }
    const transcript = String(data.transcript || "").trim();
    if (transcript) finishSpokenMarkerReply(transcript);
    else setMarkerStatus("NO SPEECH HEARD: SAY YES OR NO");
  } catch (error) {
    if (!(error instanceof DOMException && error.name === "AbortError")) {
      console.error(error);
      setMarkerStatus("LOCAL MIC CONFIRMATION FAILED");
    }
  } finally {
    markerListenAbortController = null;
    markerListening = false;
    micFilterText.textContent = micConfirm.checked ? "MIC CONFIRM" : "MIC OFF";
  }
}

function startMarkerListening() {
  if (!gameClient || !pendingMarkers.length || !micConfirm.checked || markerListening) return;
  if (voiceAbortController || currentAudio) return;
  if (localSpeechReady) {
    listenForLocalMarkerReply();
    return;
  }
  const recognition = createMarkerRecognition();
  if (recognition) {
    try {
      recognition.start();
    } catch {
      setMarkerStatus("MIC CONFIRMATION IS ALREADY STARTING");
    }
    return;
  }
  micConfirm.checked = false;
  micConfirm.disabled = true;
  micFilterText.textContent = "MIC UNSUPPORTED";
  setMarkerStatus("LOCAL SPEECH MODEL IS UNAVAILABLE");
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

async function readAnswer() {
  if (!neuralVoiceReady || !currentAnswer) return;
  stopVoice("PREPARING BRIEF");
  setVoiceState(true, "PREPARING BRIEF");
  const controller = new AbortController();
  voiceAbortController = controller;

  try {
    const response = await fetch("/voice", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text: spokenVersion(currentSpokenSummary || currentAnswer),
        voice: voiceSelect.value,
      }),
      signal: controller.signal,
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || `Voice request failed (${response.status})`);
    }
    const audioBlob = await response.blob();
    if (controller.signal.aborted) return;
    voiceAbortController = null;
    currentAudioUrl = URL.createObjectURL(audioBlob);
    const audio = new Audio(currentAudioUrl);
    currentAudio = audio;
    audio.addEventListener("play", () => setVoiceState(true, "READING BRIEF"));
    audio.addEventListener("ended", () => {
      stopVoice("NEURAL VOICE READY");
      startMarkerListening();
    });
    audio.addEventListener("error", () => stopVoice("VOICE ERROR"));
    await audio.play();
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") return;
    console.error(error);
    stopVoice("VOICE ERROR");
  }
}

function markerCommand(markers) {
  const payload = markers
    .map((marker) => {
      const icon = markerIcons[marker.icon] || markerIcons.pin;
      return `${Number(marker.x)},${Number(marker.y)},${icon.type}`;
    })
    .join(";");
  window.location.hash = `palmarkers=${Date.now()};${payload}`;
  setMarkerStatus(
    `${markers.length} MARKER${markers.length === 1 ? "" : "S"} REQUESTED IN GAME`
  );
}

function playMarkerChime() {
  markerChime.currentTime = 0;
  markerChime.play().catch(() => {
    setMarkerStatus("MARKERS PLACED / CHIME BLOCKED");
  });
}

window.palCompanionMarkerPlaced = (count) => {
  const placed = Math.max(0, Number(count) || 0);
  if (!placed) return;
  setMarkerStatus(`${placed} MARKER${placed === 1 ? "" : "S"} PLACED`);
  playMarkerChime();
};

function setMarkerStatus(message) {
  markerStatus.textContent = message;
  targetStatus.textContent = message;
}

async function copyMarker(marker) {
  const text = `${marker.x}, ${marker.y}`;
  try {
    await navigator.clipboard.writeText(text);
    setMarkerStatus(`COPIED ${text}`);
  } catch {
    setMarkerStatus(`COORDINATES ${text}`);
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
      setMarkerStatus(`${markers.length} MARKERS COPIED`);
    })
    .catch(() => {
      setMarkerStatus("COPY UNAVAILABLE");
    });
}

function finishMarkerPrompt(accepted) {
  if (!pendingMarkers.length) return;
  stopMarkerListening();
  const markers = pendingMarkers;
  pendingMarkers = [];
  markerPrompt.hidden = true;
  if (accepted) {
    activateMarkers(markers);
  } else {
    setMarkerStatus("MARKERS NOT PLACED");
  }
  question.value = "";
  question.focus();
}

function placeManualTarget() {
  const x = Number(targetX.value);
  const y = Number(targetY.value);
  if (!Number.isFinite(x) || !Number.isFinite(y) || !targetX.value || !targetY.value) {
    setMarkerStatus("ENTER X AND Y");
    return;
  }
  if (Math.abs(x) > 5000 || Math.abs(y) > 5000) {
    setMarkerStatus("COORDINATES OUT OF RANGE");
    return;
  }
  activateMarkers([{ label: "Manual target", x, y }]);
}

function renderMarkers(markers) {
  currentMarkers = markers;
  pendingMarkers = gameClient ? [...markers] : [];
  markersRoot.replaceChildren();
  markerSection.hidden = markers.length === 0;
  markerPrompt.hidden = pendingMarkers.length === 0;
  markerPromptText.textContent =
    markers.length === 1
      ? "PLACE THIS ON YOUR MAP? SAY YES OR NO."
      : `PLACE ALL ${markers.length} ON YOUR MAP? SAY YES OR NO.`;
  setMarkerStatus("");
  placeAllButton.textContent = gameClient ? "PLACE ALL" : "COPY ALL";

  markers.forEach((marker) => {
    const row = document.createElement("div");
    row.className = "marker";

    const label = document.createElement("span");
    label.className = "marker-label";
    label.textContent = marker.label;
    label.title = marker.label;

    const iconData = markerIcons[marker.icon] || markerIcons.pin;
    const icon = document.createElement("span");
    icon.className = `marker-icon ${marker.icon || "pin"}`;
    icon.textContent = iconData.glyph;
    icon.title = `${iconData.label} marker`;
    icon.setAttribute("aria-hidden", "true");

    const coordinates = document.createElement("span");
    coordinates.className = "marker-coordinates";
    coordinates.textContent = `${marker.x}, ${marker.y}`;

    const action = document.createElement("button");
    action.className = "tool-button";
    action.type = "button";
    action.textContent = gameClient ? "PLACE" : "COPY";
    action.addEventListener("click", () => activateMarkers([marker]));

    row.append(icon, label, coordinates, action);
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
    webFilterText.textContent = webConfigured ? "NETWORK LINK" : "NETWORK OFFLINE";
    webFilter.title = webConfigured
      ? "Search current Palworld web sources"
      : "Set BRAVE_SEARCH_API_KEY in the local .env file";
    neuralVoiceReady = data.voice_engine === "edge-neural";
    localSpeechReady = data.speech_engine === "windows-sapi-grammar";
    autoRead.disabled = !neuralVoiceReady;
    voiceSelect.disabled = !neuralVoiceReady;
    readButton.disabled = !neuralVoiceReady;
    voiceFilterText.textContent = neuralVoiceReady ? "VOICE RELAY" : "VOICE OFFLINE";
    if (!voiceAbortController && !currentAudio) {
      voiceStatus.textContent = neuralVoiceReady ? "NEURAL VOICE READY" : "VOICE UNAVAILABLE";
    }
  } catch {
    status.classList.add("offline");
    statusText.textContent = "COMPANION OFFLINE";
    neuralVoiceReady = false;
    autoRead.disabled = true;
    voiceSelect.disabled = true;
    readButton.disabled = true;
    stopVoice("VOICE OFFLINE");
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
  if (pendingMarkers.length && confirmMarkerPattern.test(text)) {
    finishMarkerPrompt(true);
    return;
  }
  if (pendingMarkers.length && declineMarkerPattern.test(text)) {
    finishMarkerPrompt(false);
    return;
  }

  stopMarkerListening();
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
        player_name: playerName,
        player_level: Number(playerLevel.value) || null,
      }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);

    answerText.textContent = data.text;
    currentAnswer = data.text;
    currentSpokenSummary = data.spoken_summary || data.text;
    confidence.className = `confidence ${data.confidence}`;
    confidence.textContent =
      `${data.confidence.toUpperCase()} CONFIDENCE${data.cached ? " / CACHED" : ""}`;
    renderMarkers(data.coordinates || []);
    if (gameClient && currentMarkers.length) {
      currentSpokenSummary =
        `${currentSpokenSummary} Want me to place ` +
        `${currentMarkers.length === 1 ? "this location" : "these locations"} on your map?`;
    }
    renderSources(data.sources || []);
    remember(text);
    show(answerState);
    if (autoRead.checked) readAnswer();
    else startMarkerListening();
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
  else setVoiceState(false, "NEURAL VOICE READY");
});
micConfirm.checked =
  gameClient && localStorage.getItem("pal-companion-mic-confirm") === "true";
micConfirm.disabled = !gameClient;
micFilter.title = gameClient
  ? "Listen for yes or no while a map confirmation is visible"
  : "Microphone confirmation is available in the in-game client";
micFilterText.textContent = micConfirm.disabled
  ? "MIC IN-GAME"
  : micConfirm.checked
    ? "MIC CONFIRM"
    : "MIC OFF";
micConfirm.addEventListener("change", () => {
  localStorage.setItem("pal-companion-mic-confirm", String(micConfirm.checked));
  if (micConfirm.checked) startMarkerListening();
  else stopMarkerListening();
});
voiceSelect.value = localStorage.getItem("pal-companion-voice") || "emma";
voiceSelect.addEventListener("change", () => {
  localStorage.setItem("pal-companion-voice", voiceSelect.value);
  stopVoice("NEURAL VOICE READY");
});
playerLevel.value =
  queryParams.get("level") || localStorage.getItem("pal-companion-player-level") || "";
playerLevel.addEventListener("change", () => {
  const level = Math.min(255, Math.max(1, Number(playerLevel.value) || 0));
  playerLevel.value = level || "";
  localStorage.setItem("pal-companion-player-level", playerLevel.value);
});
readButton.addEventListener("click", readAnswer);
stopVoiceButton.addEventListener("click", () => stopVoice());
placeAllButton.addEventListener("click", () => activateMarkers(currentMarkers));
confirmMarkersButton.addEventListener("click", () => finishMarkerPrompt(true));
declineMarkersButton.addEventListener("click", () => finishMarkerPrompt(false));
placeTargetButton.addEventListener("click", placeManualTarget);
vendorButton.addEventListener("click", openVendorDirectory);
storageButton.addEventListener("click", openStorageOrganizer);
closeVendorsButton.addEventListener("click", () => show(currentAnswer ? answerState : emptyState));
closeStorageButton.addEventListener("click", () => show(currentAnswer ? answerState : emptyState));
scanStorageButton.addEventListener("click", requestStorageScan);
planStorageButton.addEventListener("click", buildStoragePlan);
applyStorageButton.addEventListener("click", applyStoragePlan);
document.addEventListener("keydown", (event) => {
  if (gameClient && event.key === "Escape") {
    event.preventDefault();
    event.stopPropagation();
    window.location.hash = `palclose=${Date.now()}`;
    return;
  }
  if (event.key === "F3") {
    event.preventDefault();
    openVendorDirectory();
  }
  if (event.key === "F4") {
    event.preventDefault();
    openStorageOrganizer();
  }
});
[targetX, targetY].forEach((input) => {
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      placeManualTarget();
    }
  });
});

renderHistory();
checkHealth();
if (queryParams.get("view") === "vendors") openVendorDirectory();
if (queryParams.get("view") === "organizer") openStorageOrganizer();
window.setInterval(checkHealth, 15000);
