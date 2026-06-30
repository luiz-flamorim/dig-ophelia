let matrixRows = 0;
let matrixCols = 0;
let tileCols = 16;
let tileRows = 8;
let moduleTilesX = 1;
let moduleTilesY = 1;
let cellAspectW = 1;
let cellAspectH = 2;

const gridDisplay = document.getElementById("grid-display");
const streamImg = document.getElementById("stream");
const statusFps = document.getElementById("status-fps");
const statusBg = document.getElementById("status-bg");
const statusHost = document.getElementById("status-host");

const bgThresholdSlider = document.getElementById("bg-threshold-slider");
const thresholdValue = document.getElementById("threshold-value");
const previewBtn = document.getElementById("preview-btn");
const invertBtn = document.getElementById("invert-btn");
const bgCaptureBtn = document.getElementById("bg-capture-btn");

const probeToggleBtn = document.getElementById("probe-toggle-btn");
const probeStatus = document.getElementById("probe-status");
const probeIndexEl = document.getElementById("probe-index");
const probeDeviceEl = document.getElementById("probe-device");
const probeDigitEl = document.getElementById("probe-digit");
const probeHexEl = document.getElementById("probe-hex");
const probePrevBtn = document.getElementById("probe-prev-btn");
const probeAutoBtn = document.getElementById("probe-auto-btn");
const probeNextBtn = document.getElementById("probe-next-btn");

let invert = false;
// Cycle order for the preview button.  "background" shows the captured BG frame.
const PREVIEW_MODES = ["off", "mask", "diff", "raw", "background"];
const PREVIEW_LABELS = {
  off:        "Preview: off",
  mask:       "Preview: mask",
  diff:       "Preview: diff",
  raw:        "Preview: raw",
  background: "Preview: background",
};
let previewMode = "off";
let probeEnabled = false;
let probeAuto = false;
let settingsTimer = null;
let sliderEditing = false;
let settingsDirty = false;

init();

function buildGrid() {
  gridDisplay.innerHTML = "";
  const tilesX = moduleTilesX;
  const tilesY = moduleTilesY;
  const showIndices = matrixCols <= 16;

  for (let row = 0; row < matrixRows; row++) {
    const rowEl = document.createElement("div");
    rowEl.className = "matrix-row";

    for (let ty = 0; ty < tilesY; ty++) {
      for (let tx = 0; tx < tilesX; tx++) {
        const rowInTile = row - ty * tileRows;
        if (rowInTile < 0 || rowInTile >= tileRows) {
          continue;
        }

        const tileEl = document.createElement("div");
        tileEl.className = "tile-group";
        tileEl.dataset.tileX = tx;
        tileEl.dataset.tileY = ty;

        for (let c = 0; c < tileCols; c++) {
          const col = tx * tileCols + c;
          const cell = document.createElement("div");
          cell.className = "grid-cell";
          cell.dataset.row = row;
          cell.dataset.col = col;
          if (showIndices) {
            cell.textContent = row * matrixCols + col;
          }
          tileEl.appendChild(cell);
        }

        rowEl.appendChild(tileEl);
      }
    }

    gridDisplay.appendChild(rowEl);
  }
}

function updateSliderFill(slider) {
  const max = parseFloat(slider.max);
  const value = parseFloat(slider.value);
  const ratio = max > 0 ? value / max : 0;
  slider.parentElement.style.setProperty("--slider-value", ratio);
  if (thresholdValue) {
    thresholdValue.textContent = String(Math.round(value));
  }
}

function setMatrixLayout(rows, cols) {
  document.documentElement.style.setProperty("--matrix-rows", String(rows));
  document.documentElement.style.setProperty("--matrix-cols", String(cols));
  document.documentElement.style.setProperty("--tile-cols", String(tileCols));
  document.documentElement.style.setProperty("--cell-aspect-w", String(cellAspectW));
  document.documentElement.style.setProperty("--cell-aspect-h", String(cellAspectH));

  const isMobile = window.matchMedia("(max-width: 700px)").matches;
  const horizontalPad = isMobile ? 16 : 48;
  const availableW = Math.max(200, window.innerWidth - horizontalPad);
  const cellWidth = isMobile
    ? Math.max(9, Math.floor(availableW / cols))
    : Math.max(14, Math.min(18, Math.floor(Math.min(availableW, 640) / cols)));
  const cellSize = cellWidth;
  const panelMaxW = cols * cellWidth;

  document.documentElement.style.setProperty("--cell-size", `${cellSize}px`);
  document.documentElement.style.setProperty("--matrix-panel-max-w", `${panelMaxW}px`);
}

function setProcessedStream(enabled) {
  if (enabled) {
    streamImg.src = `/api/stream?t=${Date.now()}`;
  } else {
    streamImg.removeAttribute("src");
  }
}

function applyPreviewMode() {
  const active = previewMode !== "off";
  previewBtn.classList.toggle("active", active);
  previewBtn.textContent = PREVIEW_LABELS[previewMode] ?? "Preview: off";
  setProcessedStream(active);
}

function applyProbeUi() {
  document.body.classList.toggle("probe-mode", probeEnabled);
  probeToggleBtn.classList.toggle("active", probeEnabled);
  probeStatus.textContent = probeEnabled ? (probeAuto ? "auto" : "on") : "off";
  probePrevBtn.disabled = !probeEnabled;
  probeNextBtn.disabled = !probeEnabled;
  probeAutoBtn.disabled = !probeEnabled;
  probeAutoBtn.classList.toggle("active", probeAuto);
  if (probeEnabled && previewMode !== "off") {
    previewMode = "off";
    applyPreviewMode();
  }
}

async function postProbe(body) {
  const res = await fetch("/api/probe", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return res.json();
}

function updateProbeReadout(data) {
  if (typeof data.probe_index !== "number") return;
  probeIndexEl.textContent = String(data.probe_index);
  probeDeviceEl.textContent = String(data.probe_device ?? 0);
  probeDigitEl.textContent = String(data.probe_digit ?? 0);
  probeHexEl.textContent = String(data.probe_hex ?? "0");
}

function scheduleSettings() {
  settingsDirty = true;
  if (settingsTimer) clearTimeout(settingsTimer);
  settingsTimer = setTimeout(pushSettings, 150);
}

async function pushSettings() {
  const body = {
    bg_threshold: parseInt(bgThresholdSlider.value, 10),
    invert,
    preview_mode: previewMode,
  };

  try {
    await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    settingsDirty = false;
  } catch (err) {
    console.error("Settings update failed:", err);
  }
}

async function pollState() {
  try {
    const res = await fetch("/api/state");
    const data = await res.json();

    statusFps.textContent = probeEnabled
      ? `Probe: ${data.probe_index}/${data.probe_max}`
      : `FPS: ${data.fps.toFixed(1)}`;

    if (typeof data.probe_enabled === "boolean") {
      probeEnabled = data.probe_enabled;
      probeAuto = !!data.probe_auto;
      applyProbeUi();
      updateProbeReadout(data);
    }

    if (probeEnabled) {
      statusBg.textContent = "Background: paused";
    } else {
      statusBg.textContent = data.has_background
        ? "Background: captured"
        : "Background: none";
    }

    if (typeof data.invert === "boolean" && !settingsDirty && !probeEnabled) {
      invert = data.invert;
      invertBtn.classList.toggle("active", invert);
    }

    if (typeof data.preview_mode === "string" && !settingsDirty && !probeEnabled) {
      if (data.preview_mode !== previewMode) {
        previewMode = data.preview_mode;
        applyPreviewMode();
      }
    }

    if (
      typeof data.bg_threshold === "number" &&
      !sliderEditing &&
      !probeEnabled
    ) {
      bgThresholdSlider.value = data.bg_threshold;
      updateSliderFill(bgThresholdSlider);
    }

    const grid = data.grid;
    for (let row = 0; row < matrixRows; row++) {
      for (let col = 0; col < matrixCols; col++) {
        const cell = gridDisplay.querySelector(
          `[data-row="${row}"][data-col="${col}"]`
        );
        if (!cell) continue;
        const active = grid[row][col];
        cell.classList.toggle("active", !!active && !probeEnabled);
        cell.classList.toggle("probe-active", !!active && probeEnabled);
      }
    }
  } catch (err) {
    console.error("State poll failed:", err);
  }
}

function startSliderEdit() {
  sliderEditing = true;
}

function endSliderEdit() {
  sliderEditing = false;
}

bgThresholdSlider.addEventListener("pointerdown", startSliderEdit);
bgThresholdSlider.addEventListener("pointerup", endSliderEdit);
bgThresholdSlider.addEventListener("pointercancel", endSliderEdit);
bgThresholdSlider.addEventListener("touchstart", startSliderEdit, { passive: true });
bgThresholdSlider.addEventListener("touchend", endSliderEdit);
bgThresholdSlider.addEventListener("touchcancel", endSliderEdit);
bgThresholdSlider.addEventListener("change", () => {
  endSliderEdit();
  scheduleSettings();
});

bgThresholdSlider.addEventListener("input", () => {
  updateSliderFill(bgThresholdSlider);
  scheduleSettings();
});

previewBtn.addEventListener("click", async () => {
  // Cycle to next mode; skip "background" if no background has been captured yet
  // (the server will show a black frame anyway, but skip for cleaner UX).
  const idx = PREVIEW_MODES.indexOf(previewMode);
  const nextIdx = (idx + 1) % PREVIEW_MODES.length;
  previewMode = PREVIEW_MODES[nextIdx];
  settingsDirty = true;

  // Update stream immediately so the img src loads in parallel with the fetch.
  applyPreviewMode();

  try {
    await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        bg_threshold: parseInt(bgThresholdSlider.value, 10),
        invert,
        preview_mode: previewMode,
      }),
    });
    settingsDirty = false;
  } catch (err) {
    console.error("Settings update failed:", err);
  }
});

invertBtn.addEventListener("click", () => {
  invert = !invert;
  invertBtn.classList.toggle("active", invert);
  scheduleSettings();
});

bgCaptureBtn.addEventListener("click", async () => {
  if (probeEnabled) return;
  bgCaptureBtn.disabled = true;
  bgCaptureBtn.textContent = "Capturing...";
  try {
    await fetch("/api/background/capture", { method: "POST" });
    bgCaptureBtn.textContent = "Background captured";
    setTimeout(() => {
      bgCaptureBtn.textContent = "Capture background";
      bgCaptureBtn.disabled = false;
    }, 2000);
  } catch (err) {
    console.error("Background capture failed:", err);
    bgCaptureBtn.textContent = "Capture background";
    bgCaptureBtn.disabled = false;
  }
});

probeToggleBtn.addEventListener("click", async () => {
  try {
    const data = await postProbe({ enabled: !probeEnabled });
    probeEnabled = data.probe_enabled;
    probeAuto = data.probe_auto;
    applyProbeUi();
  } catch (err) {
    console.error("Probe toggle failed:", err);
  }
});

probePrevBtn.addEventListener("click", async () => {
  try {
    await postProbe({ step: "prev" });
  } catch (err) {
    console.error("Probe step failed:", err);
  }
});

probeNextBtn.addEventListener("click", async () => {
  try {
    await postProbe({ step: "next" });
  } catch (err) {
    console.error("Probe step failed:", err);
  }
});

probeAutoBtn.addEventListener("click", async () => {
  try {
    const data = await postProbe({ auto: !probeAuto });
    probeAuto = data.probe_auto;
    applyProbeUi();
  } catch (err) {
    console.error("Probe auto failed:", err);
  }
});

async function init() {
  try {
    const res = await fetch("/api/config");
    const cfg = await res.json();
    matrixRows = cfg.matrix_rows;
    matrixCols = cfg.matrix_cols;
    tileCols = cfg.tile_cols;
    tileRows = cfg.tile_rows;
    moduleTilesX = cfg.module_tiles_x;
    moduleTilesY = cfg.module_tiles_y;
    if (typeof cfg.cell_aspect_w === "number") cellAspectW = cfg.cell_aspect_w;
    if (typeof cfg.cell_aspect_h === "number") cellAspectH = cfg.cell_aspect_h;
    setMatrixLayout(matrixRows, matrixCols);
    statusHost.textContent = `Host: ${window.location.host}`;
    buildGrid();
    updateSliderFill(bgThresholdSlider);
    applyPreviewMode();
    applyProbeUi();
    setInterval(pollState, 120);

    window.addEventListener("resize", () => {
      setMatrixLayout(matrixRows, matrixCols);
    });
  } catch (err) {
    console.error("Config load failed:", err);
  }
}
