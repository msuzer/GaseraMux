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
            if (data.connection) window.updateFooterStatus?.(!!data.connection.online);
            window.GaseraHub.emit(data);
        } catch (err) { console.error("[SSE] parse error", err); }
    };

    window.gaseraSSE.onerror = () => {
        console.warn("[SSE] lost connection, retrying...");
        setTimeout(startGaseraSSE, 5000);
    };
}

// ---------------------------------------------------------------------
// Footer status/time
// ---------------------------------------------------------------------
window.updateFooterTime = function (timestamp) {
    const el = document.getElementById("lastUpdate");
    if (!el) return;
    el.textContent = timestamp
        ? new Date(timestamp).toLocaleTimeString("en-GB", { hour12: false })
        : "–";
};

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
// Global SSE subscription (footer reacts to every phase change)
// ---------------------------------------------------------------------
let lastPhase = null;
if (window.GaseraHub) {
    window.GaseraHub.subscribe(d => {
        const phase = d.phase || "IDLE";
        if (phase !== lastPhase) {
            lastPhase = phase;
            window.updateFooterTime(Date.now());
        }
        if (d.connection) {
            window.updateFooterStatus(!!d.connection.online);
            heartbeatFooter();
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
