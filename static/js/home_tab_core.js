// ============================================================
// Home Tab – Core Measurement Control Logic
// ============================================================
// console.log("[home_tab_core] loaded");

// ============================================================
// Buttons & indicators
// ============================================================
const btnStart = document.getElementById("btnStart");
const btnAbort = document.getElementById("btnAbort");
const buzzerToggle = document.getElementById("cfgBuzzer");

// ============================================================
// Helpers
// ============================================================
function appendLog(msg) {
  // console.log(`[${new Date().toLocaleTimeString()}] ${msg}`);
}

function showAlert(message, type = "info") {
  // remove any existing alert first
  const existing = document.getElementById("centerToast");
  if (existing) existing.remove();

  const alertBox = document.createElement("div");
  alertBox.id = "centerToast";
  alertBox.className = `center-toast ${type}`;
  alertBox.textContent = message;

  const hint = document.createElement("small");
  hint.textContent = "(click to dismiss)";
  alertBox.appendChild(hint);

  document.body.appendChild(alertBox);

  // fade in
  requestAnimationFrame(() => alertBox.classList.add("show"));

  // manual dismiss
  alertBox.addEventListener("click", () => {
    alertBox.classList.remove("show");
    alertBox.addEventListener("transitionend", () => alertBox.remove());
  });
}

// ============================================================
// Preferences
// ============================================================
window.collectPrefsData = function () {
  return {
    measurement_duration: +document.getElementById("cfgMeasure").value,
    pause_seconds: +document.getElementById("cfgPause").value,
    repeat_count: +document.getElementById("cfgRepeat").value,
    include_channels: window.getJarMask?.() ?? [],
  };
}

function loadPreferences() {
  safeFetch(API_PATHS?.settings?.read)
    .then(r => r.json())
    .then(p => {
      document.getElementById('cfgMeasure').value = p.measurement_duration ?? 300;
      document.getElementById('cfgPause').value = p.pause_seconds ?? 5;
      document.getElementById('cfgRepeat').value = p.repeat_count ?? 1;
      buzzerToggle.checked = p.buzzer_enabled ?? true;

      window.applyJarMask?.(p.include_channels ?? []);
      appendLog("[UI] Preferences loaded");
    })
    .catch(e => appendLog("[UI] Pref load failed: " + e));
}

const START_DELAY = 5;
let countdownTimer = null;
let countdown = START_DELAY;

// ============================================================
// Phase Handling
// ============================================================
function applyPhase(phase) {
  if (countdownTimer && phase !== "IDLE") {
    clearInterval(countdownTimer);
    countdownTimer = null;
    countdown = START_DELAY;
  }

  switch (phase) {
    case "IDLE":
      appendLog("System idle");
      btnStart.textContent = "Start Measurement";
      btnStart.classList.add("btn-success");
      btnStart.classList.remove("btn-warning");
      btnStart.disabled = false;
      btnAbort.disabled = true;
      break;
    case "MEASURING":
      btnStart.textContent = "Measuring";
      btnStart.disabled = true;
      btnAbort.disabled = false;
      break;
    case "PAUSED":
      btnStart.textContent = "Paused";
      btnStart.disabled = true;
      btnAbort.disabled = false;
      break;
    case "SWITCHING":
      btnStart.textContent = "Switching Channel";
      btnStart.disabled = true;
      btnAbort.disabled = false;
      break;
    case "ABORTED":
      appendLog("Measurement aborted");
      btnStart.textContent = "Start Measurement";
      btnAbort.textContent = "Aborted...";
      btnStart.classList.add("btn-success");
      btnStart.classList.remove("btn-warning");
      btnStart.disabled = false;
      btnAbort.disabled = true;
      break;
  }
}

// ============================================================
// Start/Abort
// ============================================================
btnStart.addEventListener("click", () => {
  if (window.isMeasurementRunning) {
    appendLog("Measurement already running");
    return;
  }

  countdown = START_DELAY;

  if (countdownTimer) {
    clearInterval(countdownTimer);
    countdownTimer = null;
    btnStart.textContent = "Start Measurement";
    btnStart.classList.replace("btn-warning", "btn-success");
    return;
  }

  btnStart.classList.replace("btn-success", "btn-warning");
  btnStart.textContent = `Starting in ${countdown}… (Cancel)`;
  btnAbort.textContent = "Abort";

  countdownTimer = setInterval(() => {
    if (window.isMeasurementRunning) {
      clearInterval(countdownTimer);
      return;
    }

    countdown--;
    btnStart.textContent = countdown > 0 ? `Starting in ${countdown}… (Cancel)` : "Starting…";
    if (countdown <= 0) {
      clearInterval(countdownTimer); countdownTimer = null;
      startMeasurement();
    }
  }, 1000);
});

function startMeasurement() {
  btnStart.textContent = "Starting…";
  btnStart.disabled = true;
  safeFetch(API_PATHS?.measurement?.start, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(collectPrefsData())
  })
    .then(r => r.json())
    .then(j => appendLog(j.message || "Start requested"))
    .catch(e => { appendLog("Start failed: " + e); resetToIdle(); });
}

const abortModal = new bootstrap.Modal(document.getElementById("abortConfirmModal"));
btnAbort.addEventListener("click", () => abortModal.show());

document.getElementById("confirmAbort").addEventListener("click", () => {
  abortModal.hide();
  safeFetch(API_PATHS?.measurement?.abort, { method: "POST" })
    .then(r => r.json())
    .then(j => appendLog(j.message || "Abort requested"))
    .catch(e => appendLog("Abort failed: " + e));
});

// ============================================================
// SSE Handler (delegates visuals to home_tab_visual.js)
// ============================================================
let currentChannel = -1;
let currentRep = -1;
let currentPct = 0;
let currentOverallPct = 0;
let currentPhase = null;

function SSEHandler(d) {
  try {
    const ch = d.virtual_channel ?? d.vch ?? 0;
    const rep = d.repeat_index ?? d.repeat ?? 0;
    const pct = d.percent ?? 0;
    const overallPct = d.overall_percent ?? 0;
    const newPhase = d.phase ?? "IDLE";

    const channelChanged = currentChannel !== ch;
    const phaseChanged = currentPhase !== newPhase;
    const repeatChanged = currentRep !== rep;
    const pctChanged = currentPct !== pct;
    const overallPctChanged = currentOverallPct !== overallPct;

    if (channelChanged) {
      currentChannel = ch;
      if (phaseChanged && (ch === 0)) {
        // first jar of first repeat ⇒ new run
        window.resetJarStates?.();
      }
    }

    if (phaseChanged) {
      applyPhase(newPhase);
      window.updateJarColors?.(ch, newPhase);   // visual sync
      window.updateChannelInfo?.(ch, newPhase);
      window.isMeasurementRunning = (newPhase === "MEASURING" || newPhase === "PAUSED" || newPhase === "SWITCHING");
      window.updateGridLock?.();

      // --- Pop-up notifications ---
      if (newPhase === "ABORTED") {
        showAlert("Measurement aborted.", "danger");
      } else if (currentPhase === "SWITCHING" && newPhase === "IDLE") {
        showAlert("Measurement completed successfully.", "success");
      }

      currentPhase = newPhase;
    }

    if (phaseChanged || channelChanged) {
      window.updateChannelInfo?.(ch, newPhase);
    }

    if (repeatChanged || (phaseChanged && !window.isMeasurementRunning) || (channelChanged && ch === 0 && rep === 0)) {
      currentRep = rep;
      window.updateRepeatInfo?.(currentRep);
    }

    if (pctChanged) {
      currentPct = pct;
      window.updateCircularProgress?.("runCircle", "runPct", currentPct);
    }

    if (overallPctChanged) {
      currentOverallPct = overallPct;
      window.updateCircularProgress?.("overallCircle", "overallPct", currentOverallPct);
    }
  } catch (err) {
    appendLog("SSE parse error: " + err);
  }
}

function initBuzzerToggle() {
  buzzerToggle.addEventListener("change", async () => {
    const enabled = buzzerToggle.checked;
    try {
      const res = await safeFetch("/system/buzzer", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled }),
      });
      const j = await res.json();
      if (j.ok) {
        appendLog(`[UI] Buzzer ${j.enabled ? "enabled" : "disabled"} live`);
      } else {
        appendLog("[UI] Buzzer update failed: " + (j.error || "unknown"));
      }
    } catch (err) {
      appendLog("[UI] Buzzer update error: " + err);
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  loadPreferences();
  applyPhase("IDLE");
  initBuzzerToggle();
  window.GaseraHub?.subscribe(SSEHandler);
});
