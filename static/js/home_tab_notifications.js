// ============================================================
// Home Tab – Notifications & Alerts
// ============================================================
// console.log("[home_tab_notifications] loaded");

// ============================================================
// Toast Notifications
// ============================================================
function showAlert(message, type = "info") {
  // Persist dismissal within current measurement cycle only
  const ALERT_SESSION_KEY = "dismissedAlerts";
  const idKey = `${type}:${message}`;
  let dismissed = {};
  try {
    dismissed = JSON.parse(sessionStorage.getItem(ALERT_SESSION_KEY) || "{}");
  } catch { }

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
    } catch { }
  });
}

// ============================================================
// Measurement Summary Toast
// ============================================================
function showMeasurementSummaryToast(title, completedSteps, totalSteps, type) {
  const formattedTime = window.getMeasurementTiming?.();
  const summary = `<strong>${title}</strong><br>Completed: ${completedSteps}/${totalSteps} steps<br>Duration: ${formattedTime}`;
  showAlert(summary, type);
}

// Expose globally
window.showAlert = showAlert;
window.showMeasurementSummaryToast = showMeasurementSummaryToast;
