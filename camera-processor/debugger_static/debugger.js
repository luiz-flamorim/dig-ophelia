let matrixRows = 0;
let matrixCols = 0;

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

let invert = false;
let showProcessed = false;
let settingsTimer = null;
let sliderEditing = false;
let settingsDirty = false;

init();

function buildGrid() {
  gridDisplay.innerHTML = "";
  for (let row = 0; row < matrixRows; row++) {
    const rowEl = document.createElement("div");
    rowEl.className = "matrix-row";
    for (let col = 0; col < matrixCols; col++) {
      const cell = document.createElement("div");
      cell.className = "grid-cell";
      cell.dataset.row = row;
      cell.dataset.col = col;
      cell.textContent = row * matrixCols + col;
      rowEl.appendChild(cell);
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

function setMatrixAspect(rows, cols) {
  document.documentElement.style.setProperty("--matrix-rows", String(rows));
  document.documentElement.style.setProperty("--matrix-cols", String(cols));
}

function setProcessedStream(enabled) {
  if (enabled) {
    streamImg.src = `/api/stream?t=${Date.now()}`;
  } else {
    streamImg.removeAttribute("src");
  }
}

function applyPreviewState() {
  previewBtn.classList.toggle("active", showProcessed);
  setProcessedStream(showProcessed);
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
    show_processed: showProcessed,
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

    statusFps.textContent = `FPS: ${data.fps.toFixed(1)}`;
    statusBg.textContent = data.has_background ? "Background: captured" : "Background: none";

    if (typeof data.invert === "boolean" && !settingsDirty) {
      invert = data.invert;
      invertBtn.classList.toggle("active", invert);
    }

    if (typeof data.show_processed === "boolean" && !settingsDirty) {
      if (data.show_processed !== showProcessed) {
        showProcessed = data.show_processed;
        applyPreviewState();
      }
    }

    if (
      typeof data.bg_threshold === "number" &&
      !sliderEditing &&
      !settingsDirty
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
        cell.classList.toggle("active", !!active);
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
  showProcessed = !showProcessed;
  previewBtn.classList.toggle("active", showProcessed);
  settingsDirty = true;
  if (!showProcessed) {
    setProcessedStream(false);
  }
  try {
    await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        bg_threshold: parseInt(bgThresholdSlider.value, 10),
        invert,
        show_processed: showProcessed,
      }),
    });
    settingsDirty = false;
    if (showProcessed) {
      setProcessedStream(true);
    }
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

async function init() {
  try {
    const res = await fetch("/api/config");
    const cfg = await res.json();
    matrixRows = cfg.matrix_rows;
    matrixCols = cfg.matrix_cols;
    setMatrixAspect(matrixRows, matrixCols);
    statusHost.textContent = `Host: ${window.location.host}`;
    buildGrid();
    updateSliderFill(bgThresholdSlider);
    applyPreviewState();
    setInterval(pollState, 100);
  } catch (err) {
    console.error("Config load failed:", err);
  }
}
