// ============================================================
// Home Tab – Core Measurement Control Logic
// ============================================================
// Requires: home_tab_dom.js (for btnStart, btnAbort, configForm)
// console.log("[home_tab_core] loaded");

// Prevent form submission
if (configForm) {
  configForm.addEventListener("submit", (e) => {
    e.preventDefault();
    return false;
  });
}

const START_DELAY = 5;
let countdownTimer = null;
let countdown = START_DELAY;

// ============================================================
// Phase Handling & UI Updates
// ============================================================
function applyPhase(phase) {
  if (countdownTimer && phase !== window.PHASE.IDLE) {
    clearInterval(countdownTimer);
    countdownTimer = null;
    countdown = START_DELAY;
  }

  const isRunning = window.isActivePhase(phase);

  // Update button states
  btnStart.disabled = true;
  btnStart.dataset.previousPhase = btnStart.dataset.phase || null;
  btnStart.dataset.phase = phase;
  btnStart.classList.remove("btn-success", "btn-warning");
  
  if (phase === window.PHASE.IDLE || phase === window.PHASE.ABORTED) {
    btnStart.textContent = "Start Measurement";
    btnStart.classList.add("btn-success");
    btnStart.disabled = false;
    btnStart.dataset.phase = "";
    btnStart.dataset.previousPhase = null;
    if (phase === window.PHASE.ABORTED) {
      btnAbort.textContent = "Aborted...";
    }
  }

  btnAbort.disabled = !btnStart.disabled;

  // Lock/unlock preference inputs
  window.lockPreferenceInputs?.(isRunning);
}

// ============================================================
// Button Display Updates
// ============================================================
function updateButtonText(btnElement, formattedTime = null) {
  if (!btnElement || !btnElement.dataset.phase) return;
  
  const currentCh = window.latestCurrentChannel ?? 0;
  const nextCh = window.latestNextChannel ?? 1;
  const phase = btnElement.dataset.phase;
  
  // Get phase text
  let phaseText = "";
  if (phase === window.PHASE.MEASURING) {
    phaseText = `${window.getPhaseText(phase)} Ch${currentCh + 1}`;
  } else if (phase === window.PHASE.PAUSED) {
    phaseText = `${window.getPhaseText(phase)} Ch${currentCh + 1}`;
  } else if (phase === window.PHASE.HOMING) {
    phaseText = window.getPhaseText(phase);
  } else if (phase === window.PHASE.SWITCHING) {
    phaseText = `${window.getPhaseText(phase)} Ch${currentCh + 1} → Ch${nextCh + 1}`;
  }
  
  // Append timer if provided
  if (formattedTime) {
    btnElement.textContent = `${phaseText} • ${formattedTime}`;
  } else if (phaseText) {
    btnElement.textContent = phaseText;
  }
}

// Expose globally for core_index timer updates
window.updateButtonText = updateButtonText;

// ============================================================
// Start/Abort
// ============================================================
btnStart.addEventListener("click", () => {
  if (window.isMeasurementRunning) {
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
    .then(j => {
      if (!j.ok) {
        // Show error message to user
        window.showAlert?.(j.message || "Failed to start measurement", "warning");
        
        // Reset button to enabled state
        btnStart.textContent = "Start Measurement";
        btnStart.classList.replace("btn-warning", "btn-success");
        btnStart.disabled = false;
        
        console.warn("[MEAS] Start error:", j.message);
      }
    })
    .catch(e => {
      // Handle network errors
      window.showAlert?.("Network error: " + (e.message || "Unknown error"), "danger");
      
      // Reset button to enabled state
      btnStart.textContent = "Start Measurement";
      btnStart.classList.replace("btn-warning", "btn-success");
      btnStart.disabled = false;
      
      console.warn("[MEAS] Start failed:", e);
    });
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
        .then(j => {
          if (!j.ok) {
            window.showAlert?.(j.message || "Failed to abort measurement", "warning");
            console.warn("[MEAS] Abort error:", j.message);
          }
        })
        .catch(e => {
          window.showAlert?.("Abort error: " + (e.message || "Unknown error"), "danger");
          console.warn("[MEAS] Abort failed:", e);
        });
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
    const newPhase = d.phase ?? window.PHASE.IDLE;
    const stepIndex = d.step_index ?? 0;
    const enabledCount = d.enabled_count ?? 0;
    const repeatTotal = d.repeat_total ?? 0;
    const totalSteps = d.total_steps ?? 0;
    const buzzer_enabled = d.buzzer_enabled ?? null;

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
      window.isMeasurementRunning = window.isActivePhase(newPhase);
      window.updateGridLock?.();

      if (window.isActivePhase(newPhase)) {
        window.updateETTTDisplay?.();
      }

      // Show completion/abort notifications
      if (newPhase === window.PHASE.ABORTED) {
        window.showMeasurementSummaryToast?.("Measurement Aborted", stepIndex, totalSteps, "danger");
      } else if (currentPhase === window.PHASE.SWITCHING && newPhase === window.PHASE.IDLE) {
        window.showMeasurementSummaryToast?.("Measurement Complete", totalSteps, totalSteps, "success");
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

  // Subscribe to SSE updates and sync buzzer state from other clients
    if (buzzer_enabled !== null && buzzerToggle.checked !== buzzer_enabled) {
      buzzerToggle.checked = buzzer_enabled;
    }

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

document.addEventListener("DOMContentLoaded", () => {
  window.loadPreferences?.();
  applyPhase(window.PHASE.IDLE);
  window.GaseraHub?.subscribe(SSEHandler);
});
