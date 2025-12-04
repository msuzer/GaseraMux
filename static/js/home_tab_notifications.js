// ============================================================
// Home Tab – Notifications & Alerts
// ============================================================
// console.log("[home_tab_notifications] loaded");

// ============================================================
// Toast Notifications
// ============================================================
function showAlert(message, type = "info") {
  const isError = type === "warning" || type === "danger";

  // Remove existing alert
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

  // Fade in
  requestAnimationFrame(() => alertBox.classList.add("show"));

  // Errors auto-fade after 5 seconds; summaries stay until clicked
  if (isError) {
    setTimeout(() => {
      if (alertBox.parentElement) {
        alertBox.classList.remove("show");
        alertBox.addEventListener("transitionend", () => alertBox.remove());
      }
    }, 5000);
  }

  // Manual dismiss (click anytime)
  alertBox.addEventListener("click", () => {
    alertBox.classList.remove("show");
    alertBox.addEventListener("transitionend", () => alertBox.remove());
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
