// ============================================================
// Home Tab – Notifications & Alerts
// ============================================================
// console.log("[home_tab_notifications] loaded");

// ============================================================
// Toast Notifications
// ============================================================
function showAlert(message, type = "info") {
  window.showToast({
    message,
    variant: type,
    position: 'center',
    autohide: type === 'info' ? false : true,
    delay: 5000
  });
}

// ============================================================
// Measurement Summary Toast
// ============================================================
function showMeasurementSummaryToast(title, completedSteps, totalSteps, type) {
  const formattedTime = window.getMeasurementTiming?.();
  const summary = `<strong>${title}</strong><br>Completed: ${completedSteps}/${totalSteps} steps<br>Duration: ${formattedTime}`;
  window.showToast({
    message: summary,
    variant: type,
    position: 'center',
    autohide: false,
    delay: 5000
  });
}

// Expose globally
window.showAlert = showAlert;
window.showMeasurementSummaryToast = showMeasurementSummaryToast;
