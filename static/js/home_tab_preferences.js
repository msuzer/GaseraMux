// ============================================================
// Home Tab – Preferences Management
// ============================================================
// Requires: home_tab_dom.js (for input elements)
// console.log("[home_tab_preferences] loaded");

// ============================================================
// Collect Preferences
// ============================================================
window.collectPrefsData = function () {
  return {
    measurement_duration: +measureInput.value,
    pause_seconds: +pauseInput.value,
    repeat_count: +repeatInput.value,
    include_channels: window.getJarMask?.() ?? [],
    online_mode_enabled: onlineModeToggle?.checked ?? true,
  };
};

// ============================================================
// Load Preferences
// ============================================================
function loadPreferences() {
  safeFetch(API_PATHS?.settings?.read)
    .then(r => r.json())
    .then(p => {
      measureInput.value = p.measurement_duration ?? 300;
      pauseInput.value = p.pause_seconds ?? 5;
      repeatInput.value = p.repeat_count ?? 1;
      buzzerToggle.checked = p.buzzer_enabled ?? true;
      if (onlineModeToggle) {
        onlineModeToggle.checked = p.online_mode_enabled ?? true;
      }

      window.applyJarMask?.(p.include_channels ?? []);
    })
    .catch(e => console.warn("[UI] Pref load failed:", e));
}

// Expose globally
window.loadPreferences = loadPreferences;

// ============================================================
// Preference Input Locking
// ============================================================
window.lockPreferenceInputs = function (locked) {
  const inputs = [measureInput, pauseInput, repeatInput, onlineModeToggle];
  const tooltip = "Disabled during measurement";

  inputs.forEach(input => {
    if (input) {
      input.disabled = locked;
      if (locked) {
        input.title = tooltip;
      } else {
        input.removeAttribute("title");
      }
    }
  });
};

// ============================================================
// Buzzer Toggle
// ============================================================
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

// ============================================================
// Boot
// ============================================================
document.addEventListener("DOMContentLoaded", () => {
  loadPreferences();
  initBuzzerToggle();
});
