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
const onlineModeToggle = document.getElementById("cfgOnlineMode");

// Prevent form submission
const configForm = document.getElementById("configForm");
if (configForm) {
  configForm.addEventListener("submit", (e) => {
    e.preventDefault();
    return false;
  });
}

// ============================================================
// Helpers
// ============================================================

function showMeasurementSummaryToast(title, completedSteps, totalSteps, type) {
  const formattedTime = getMeasurementTiming();
  const summary = `<strong>${title}</strong><br>Completed: ${completedSteps}/${totalSteps} steps<br>Duration: ${formattedTime}`;
  showAlert(summary, type);
}

function showAlert(message, type = "info") {
  // Persist dismissal within current measurement cycle only
  const ALERT_SESSION_KEY = "dismissedAlerts";
  const idKey = `${type}:${message}`;
  let dismissed = {};
  try {
    dismissed = JSON.parse(sessionStorage.getItem(ALERT_SESSION_KEY) || "{}");
  } catch {}
  
  // Check if this specific alert was dismissed in current cycle
  const currentCycle = sessionStorage.getItem("measurementCycle") || "0";
  const dismissKey = `${currentCycle}:${idKey}`;
  
  if (dismissed[dismissKey]) {
    return; // already dismissed in this cycle
  }

  // remove any existing alert first
  const existing = document.getElementById("centerToast");
  if (existing) existing.remove();

  const alertBox = document.createElement("div");
  alertBox.id = "centerToast";
  alertBox.className = `center-toast ${type}`;
  
  // Support HTML content (for multi-line summaries)
  if (message.includes('<')) {
    alertBox.innerHTML = message;
  } else {
    alertBox.textContent = message;
  }

  const hint = document.createElement("small");
  hint.textContent = "(click to dismiss)";
  hint.style.display = "block";
  hint.style.marginTop = "0.5rem";
  alertBox.appendChild(hint);

  document.body.appendChild(alertBox);

  // fade in
  requestAnimationFrame(() => alertBox.classList.add("show"));

  // manual dismiss
  alertBox.addEventListener("click", () => {
    alertBox.classList.remove("show");
    alertBox.addEventListener("transitionend", () => alertBox.remove());
    // remember dismissal for this measurement cycle
    dismissed[dismissKey] = true;
    try {
      sessionStorage.setItem(ALERT_SESSION_KEY, JSON.stringify(dismissed));
    } catch {}
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
      if (onlineModeToggle) {
        onlineModeToggle.checked = p.online_mode_enabled ?? true;
      }

      window.applyJarMask?.(p.include_channels ?? []);
    })
    .catch(e => console.warn("[UI] Pref load failed:", e));
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

  btnStart.disabled = true;
  btnStart.dataset.previousPhase = btnStart.dataset.phase || null;
  btnStart.dataset.phase = phase;
  btnStart.classList.remove("btn-success", "btn-warning");
  if (phase === "IDLE"  || phase === "ABORTED") {
    btnStart.textContent = "Start Measurement";
      btnStart.classList.add("btn-success");
      btnStart.disabled = false;
      btnStart.dataset.phase = "";
      btnStart.dataset.previousPhase = null;
    if (phase === "ABORTED") {
      btnAbort.textContent = "Aborted...";
    }
  }

  btnAbort.disabled = !btnStart.disabled;
}

// ============================================================
// Start/Abort
// ============================================================
btnStart.addEventListener("click", () => {
  if (window.isMeasurementRunning) {
    // Measurement already running
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
  const currentCycle = parseInt(sessionStorage.getItem("measurementCycle") || "0", 10);
  sessionStorage.setItem("measurementCycle", (currentCycle + 1).toString());
  
  btnStart.textContent = "Starting…";
  btnStart.disabled = true;
  safeFetch(API_PATHS?.measurement?.start, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(collectPrefsData())
  })
    .then(r => r.json())
    .then(j => { if (!j.ok) console.warn("[MEAS] Start error:", j.message); })
    .catch(e => console.warn("[MEAS] Start failed:", e));
}

btnAbort.addEventListener("click", () => {
  window.showConfirmModal({
    title: "Confirm Abort",
    message: "Abort current measurement? This will immediately stop Gasera operation.",
    confirmText: "Yes, Abort",
    confirmClass: "btn-danger",
    headerClass: "bg-warning-subtle",
    onConfirm: () => {
      safeFetch(API_PATHS?.measurement?.abort, { method: "POST" })
        .then(r => r.json())
        .then(j => { if (!j.ok) console.warn("[MEAS] Abort error:", j.message); })
        .catch(e => console.warn("[MEAS] Abort failed:", e));
    }
  });
});

// ============================================================
// SSE Handler - Progress updates from backend
// ============================================================
let currentChannel = -1;
let currentPhase = null;

function SSEHandler(d) {
  try {
    // Extract data from SSE payload
    const ch = d.current_channel ?? 0;
    const rep = d.repeat_index ?? d.repeat ?? 0;
    const pct = d.percent ?? 0;
    const overallPct = d.overall_percent ?? 0;
    const newPhase = d.phase ?? "IDLE";
    const stepIndex = d.step_index ?? 0;
    const enabledCount = d.enabled_count ?? 0;
    const repeatTotal = d.repeat_total ?? 0;
    const totalSteps = d.total_steps ?? 0;
    
    // Store for timer/display updates
    window.latestElapsedSeconds = d.elapsed_seconds ?? 0;
    window.latestTtSeconds = d.tt_seconds ?? 0;
    window.latestNextChannel = d.next_channel ?? 0;
    window.latestCurrentChannel = ch;

    const channelChanged = currentChannel !== ch;
    const phaseChanged = currentPhase !== newPhase;

    if (channelChanged) {
      currentChannel = ch;
      if (phaseChanged && (ch === 0)) {
        window.resetJarStates?.();
      }
    }

    if (phaseChanged) {
      applyPhase(newPhase);
      window.updateJarColors?.(ch, newPhase);
      window.isMeasurementRunning = window.isActivePhase ? window.isActivePhase(newPhase) : (newPhase === "MEASURING" || newPhase === "PAUSED" || newPhase === "SWITCHING" || newPhase === "HOMING");
      window.updateGridLock?.();

      if (window.isActivePhase(newPhase)) {
        window.updateETTTDisplay?.();
      }

      // Show completion/abort notifications
      if (newPhase === "ABORTED") {
        showMeasurementSummaryToast("Measurement Aborted", stepIndex, totalSteps, "danger");
      } else if (currentPhase === "SWITCHING" && newPhase === "IDLE") {
        showMeasurementSummaryToast("Measurement Complete", totalSteps, totalSteps, "success");
      }

      currentPhase = newPhase;
    }

    if (phaseChanged || channelChanged) {
      window.updateChannelInfo?.(ch, newPhase);
    }

    // Update progress circles on every SSE event (idempotent)
    window.updateRepeatInfo?.(rep, repeatTotal);
    window.updateCycleProgress?.(pct, stepIndex, enabledCount);
    window.updateCircularProgress?.(overallPct);

  } catch (err) {
    console.warn("[SSE] parse error:", err);
  }
}

function initBuzzerToggle() {
  buzzerToggle.addEventListener("change", async () => {
    const enabled = buzzerToggle.checked;
    try {
      const res = await safeFetch(API_PATHS?.settings?.buzzer, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled }),
      });
      const j = await res.json();
      if (!j.ok) console.warn("[UI] Buzzer update failed:", j.error || "unknown");
    } catch (err) {
      console.warn("[UI] Buzzer update error:", err);
    }
  });
}


function initOnlineModeToggle() {
  if (!onlineModeToggle) return;
  onlineModeToggle.addEventListener("change", async () => {
    const enabled = onlineModeToggle.checked;
    try {
      const res = await safeFetch(API_PATHS?.settings?.online_mode, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled }),
      });
      const j = await res.json();
      if (!j.ok) console.warn("[UI] Online mode update failed:", j.error || "unknown");
    } catch (err) {
      console.warn("[UI] Online mode update error:", err);
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  loadPreferences();
  applyPhase("IDLE");
  initBuzzerToggle();
  initOnlineModeToggle();
  window.GaseraHub?.subscribe(SSEHandler);
});
