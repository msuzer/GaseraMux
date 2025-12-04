// ============================================================
// Core UI Logic – Global SSE, Footer, and Utilities
// ============================================================
// console.log("[core_index] loaded");

// ---------------------------------------------------------------------
// Shared event hub for all tabs
// ---------------------------------------------------------------------
window.GaseraHub = {
    callbacks: new Set(),
    subscribe(cb) { if (typeof cb === "function") this.callbacks.add(cb); },
    unsubscribe(cb) { this.callbacks.delete(cb); },
    emit(data) {
        this.callbacks.forEach(cb => {
            try { cb(data); } catch (err) { console.error("[GaseraHub]", err); }
        });
    }
};

// ---------------------------------------------------------------------
// Reusable Confirmation Modal
// ---------------------------------------------------------------------
window.showConfirmModal = function(options = {}) {
  const {
    title = "Confirm Action",
    message = "Are you sure you want to proceed?",
    confirmText = "Confirm",
    cancelText = "Cancel",
    confirmClass = "btn-danger",
    headerClass = "bg-warning-subtle",
    onConfirm = null
  } = options;

  // Get modal elements
  const modalEl = document.getElementById('globalConfirmModal');
  const titleEl = document.getElementById('globalConfirmModalTitle');
  const messageEl = document.getElementById('globalConfirmModalMessage');
  const headerEl = document.getElementById('globalConfirmModalHeader');
  const confirmBtn = document.getElementById('globalConfirmBtn');
  const cancelBtn = document.getElementById('globalConfirmCancelBtn');

  if (!modalEl) {
    console.error('[showConfirmModal] Modal element not found');
    return;
  }

  // Configure modal content
  titleEl.textContent = title;
  messageEl.textContent = message;
  confirmBtn.textContent = confirmText;
  cancelBtn.textContent = cancelText;

  // Update styling
  headerEl.className = `modal-header ${headerClass}`;
  confirmBtn.className = `btn ${confirmClass}`;

  // Show/hide cancel button
  cancelBtn.style.display = cancelText ? '' : 'none';

  // Remove old listeners by cloning
  const newConfirmBtn = confirmBtn.cloneNode(true);
  confirmBtn.parentNode.replaceChild(newConfirmBtn, confirmBtn);

  // Add new confirm listener
  newConfirmBtn.addEventListener('click', () => {
    const modal = bootstrap.Modal.getInstance(modalEl);
    if (modal) modal.hide();
    if (typeof onConfirm === 'function') {
      onConfirm();
    }
  });

  // Show modal
  const modal = new bootstrap.Modal(modalEl);
  modal.show();
};

// ---------------------------------------------------------------------
// Safe fetch with retry protection & UI alert
// ---------------------------------------------------------------------
let _fetchErrors = 0;
let _fetchDisabled = false;
const _MAX_FETCH_ERRORS = 3;

window.safeFetch = async function (url, options = {}) {
  if (_fetchDisabled) {
    throw new Error("fetch disabled after repeated failures");
  }

  try {
    const res = await fetch(url, options);

    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }

    // success → reset counter
    _fetchErrors = 0;
    hideFetchError();
    return res;

  } catch (err) {
    _fetchErrors++;

    // Disable further fetches if too many consecutive errors
    if (_fetchErrors >= _MAX_FETCH_ERRORS && !_fetchDisabled) {
      _fetchDisabled = true;
      console.error("⚠️ safeFetch disabled after repeated errors:", err);
    }

    showFetchErrorOnce();
    throw err;
  }
};

// ---------------------------------------------------------------------
// Show a one-time red banner if connection lost
// ---------------------------------------------------------------------
function showFetchErrorOnce() {
  if (document.getElementById("fetch-error-box")) return;

  const box = document.createElement("div");
  box.id = "fetch-error-box";
  box.className = "alert alert-danger text-center fixed-top m-0";
  box.style.zIndex = "9999";
  box.textContent = "❌ Lost connection to server. Please refresh the page.";
  document.body.prepend(box);
}

function hideFetchError() {
  const box = document.getElementById("fetch-error-box");
  if (box) box.remove();
}

// ---------------------------------------------------------------------
// SSE Setup
// ---------------------------------------------------------------------
function startGaseraSSE() {
    if (window.gaseraSSE) try { window.gaseraSSE.close(); } catch { }
    window.gaseraSSE = new EventSource(API_PATHS?.measurement?.events);

    window.gaseraSSE.onmessage = e => {
        try {
            const data = JSON.parse(e.data || "{}");
            window.GaseraHub.emit(data);
        } catch (err) { console.error("[SSE] parse error", err); }
    };

    window.gaseraSSE.onerror = () => {
        console.warn("[SSE] lost connection, retrying...");
        setTimeout(startGaseraSSE, 5000);
    };
}

// ---------------------------------------------------------------------
// Footer status
// ---------------------------------------------------------------------
window.updateFooterStatus = function (isOnline) {
    const footer = document.querySelector(".status-footer");
    const icon = document.getElementById("connIcon");
    const text = document.getElementById("connStatus");
    if (!footer || !icon || !text) return;
    if (isOnline) {
        footer.classList.add("online"); footer.classList.remove("offline");
        icon.className = "bi bi-wifi";
        text.textContent = "Gasera Online";
    } else {
        footer.classList.add("offline"); footer.classList.remove("online");
        icon.className = "bi bi-wifi-off";
        text.textContent = "Gasera Offline";
    }
};

function heartbeatFooter() {
    const icon = document.getElementById("connIcon");
    if (!icon) return;
    icon.classList.remove("beat");
    void icon.offsetWidth;
    icon.classList.add("beat");
}

// ---------------------------------------------------------------------
// ET/TT Timer Management
// ---------------------------------------------------------------------
let etttTimer = null;

function formatDuration(seconds, fixed = false, ceil = false) {
    if (!Number.isFinite(seconds) || seconds < 0) return "--:--";
    const elapsed = ceil ? Math.ceil(seconds) : Math.floor(seconds);
    const hours = Math.floor(elapsed / 3600);
    const minutes = Math.floor((elapsed % 3600) / 60);
    const secs = elapsed % 60;
    if (fixed || hours > 0) {
        return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
    }
    return `${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

// Expose globally for use in other modules
window.formatDuration = formatDuration;

function formatConsistentPair(etSeconds, ttSeconds) {
    const et = Number.isFinite(etSeconds) && etSeconds >= 0 ? etSeconds : null;
    const tt = Number.isFinite(ttSeconds) && ttSeconds >= 0 ? ttSeconds : null;
    const showHours = (et || 0) >= 3600 || (tt || 0) >= 3600;
    return [
        et !== null ? formatDuration(et, showHours) : "--:--",
        tt !== null ? formatDuration(tt, showHours) : "--:--"
    ];
}

function getMeasurementTiming() {
    const elapsed = window.latestElapsedSeconds || 0;
    const total = window.latestTtSeconds || 0;
    const [elapsedStr, totalStr] = formatConsistentPair(elapsed, total);
    return `${elapsedStr} / ${totalStr}`;
}

// Expose globally for use in other modules
window.getMeasurementTiming = getMeasurementTiming;

function updateETTTDisplay() {
    // Lazy cache DOM elements
    if (!cachedDisplay) cachedDisplay = document.getElementById("etttDisplay");
    if (!cachedBtnStart) cachedBtnStart = document.getElementById("btnStart");
    
    const formattedTime = getMeasurementTiming();
    
    // Update footer display
    if (cachedDisplay) cachedDisplay.textContent = formattedTime;
    
    // Update button text with phase + channel + timing
    if (cachedBtnStart) window.updateButtonText?.(cachedBtnStart, formattedTime);
}

function startETTTTimer(total) {
    stopETTTTimer();

    const timingDisplay = document.getElementById("timingDisplay");
    if (timingDisplay) timingDisplay.style.display = "flex";

    // applyPhase() already updates button text, just start the interval
    etttTimer = setInterval(updateETTTDisplay, 1000);
}

function stopETTTTimer() {
    if (etttTimer) {
        clearInterval(etttTimer);
        etttTimer = null;
    }
    
    // Clear DOM cache
    cachedDisplay = null;
    cachedBtnStart = null;

    const timingDisplay = document.getElementById("timingDisplay");
    if (timingDisplay) timingDisplay.style.display = "none";
}

// ---------------------------------------------------------------------
// Global SSE subscription (footer reacts to every phase change)
// -----------------------------------------------------------------------
if (window.GaseraHub) {
    window.GaseraHub.subscribe(d => {
        const phase = d.phase || window.PHASE.IDLE;
        
        if (d.connection) {
            window.updateFooterStatus(!!d.connection.online);
            heartbeatFooter();
        }
        
        // ET/TT timer management - start on SWITCHING (includes homing) to stay in sync
        const shouldStartTimer = window.isActivePhase(phase) && !etttTimer && d.tt_seconds;
        const shouldStopTimer = !window.isActivePhase(phase) && (etttTimer || document.getElementById("timingDisplay")?.style.display !== "none");
        
        if (shouldStartTimer) {
            startETTTTimer(d.tt_seconds);
        } else if (shouldStopTimer) {
            stopETTTTimer();
        }
    });
}

// ---------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
    const resultsTab = document.querySelector("#results-tab");
    resultsTab?.addEventListener("shown.bs.tab", () => {
        try { window.liveChart?.resize?.(); } catch { }
    });
    startGaseraSSE();
    // console.log("[core_index] SSE started");
});
