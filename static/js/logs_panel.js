// ============================================================
// Logs Panel – File List, Download, Delete, Storage Info
// ============================================================

// Pagination state
let currentPage = 1;
let totalPages = 1; // corrected stray double semicolon
const PAGE_SIZE = 10; // consider making user configurable later

// Toast timing constant
const TOAST_DELAY_MS = 2000;

// Track previous USB state so we don't double-fire events
window.lastUsbMounted = null;

// Debounce helper (simple trailing debounce)
function debounce(fn, wait = 400) {
  let t;
  return function (...args) {
    clearTimeout(t);
    t = setTimeout(() => fn.apply(this, args), wait);
  };
}

const debouncedRefresh = debounce(() => {
  refreshLogs();
  refreshStorageInfo();
}, 400);

// Initial immediate hide (defer scripts run post-parse)
(() => {
  const tbl = document.getElementById("logTable");
  const nl = document.getElementById("noLogsMsg");
  if (tbl) tbl.style.display = "none";
  if (nl) nl.style.display = "none";
})();

document.addEventListener("DOMContentLoaded", () => {
  // Subscribe to SSE events
  if (window.GaseraHub) {
    window.GaseraHub.subscribe(onSSEUpdateEvent);
  }

  // Bind pagination after DOM ready
  const firstBtn = document.getElementById("firstPage");
  const prevBtn = document.getElementById("prevPage");
  const nextBtn = document.getElementById("nextPage");
  const lastBtn = document.getElementById("lastPage");

  firstBtn && (firstBtn.onclick = () => { if (currentPage !== 1) { currentPage = 1; refreshLogs(); } });
  prevBtn && (prevBtn.onclick = () => { if (currentPage > 1) { currentPage--; refreshLogs(); } });
  nextBtn && (nextBtn.onclick = () => { if (currentPage < totalPages) { currentPage++; refreshLogs(); } });
  lastBtn && (lastBtn.onclick = () => { if (currentPage !== totalPages) { currentPage = totalPages; refreshLogs(); } });

  // Refresh logs when Results tab becomes active
  const resultsTabButton = document.getElementById("results-tab");
  if (resultsTabButton) {
    resultsTabButton.addEventListener("shown.bs.tab", () => {
      refreshLogs();
      refreshStorageInfo();
    });
  }
});

function onSSEUpdateEvent(event) {
  if (!event) return;

  let refresh = false;

  if (typeof event.usb_mounted === "boolean") {
    if (window.lastUsbMounted !== null && event.usb_mounted !== window.lastUsbMounted) {
      if (event.usb_mounted) {
        showUSBToast("USB drive mounted", "success");
      } else {
        showUSBToast("USB drive removed", "warning");
      }
      refresh = true;
    }

    window.lastUsbMounted = event.usb_mounted;
  }

  if (event.phase === "IDLE" || event.phase === "ABORTED") {
    refresh = true;
  }

  if (refresh) {
      debouncedRefresh();
  }
}

function showUSBToast(message, type = "info") {
  const containerId = "usb-toast-container";

  // Create toast container if missing
  let container = document.getElementById(containerId);
  if (!container) {
    container = document.createElement("div");
    container.id = containerId;
    container.className = "usb-toast-container";
    document.body.appendChild(container);
  }

  // Toast wrapper
  const toastEl = document.createElement("div");
  toastEl.className = `toast usb-toast usb-toast-${type}`;
  toastEl.role = "alert";

  toastEl.innerHTML = `
    <div class="toast-body">
      ${message}
    </div>
  `;

  container.appendChild(toastEl);

  // Activate bootstrap toast
  const toast = new bootstrap.Toast(toastEl, {
    delay: TOAST_DELAY_MS,
    autohide: true
  });

  toast.show();

  toastEl.addEventListener("hidden.bs.toast", () => toastEl.remove());
}

// Refresh Storage Info
function refreshStorageInfo() {
  const el = document.getElementById("storageInfo");
  if (!el) return;

  safeFetch(API_PATHS?.logs?.storage)
    .then(r => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    })
    .then(data => {
      if (!data.ok) throw new Error("Backend reported failure");

      const { usb, internal } = data;
      const fmt = n => n == null ? "-" : (n / (1024 ** 3)).toFixed(1) + " GB";

      if (usb && usb.mounted) {
        el.textContent = `🟢 USB Storage — ${fmt(usb.free)} free / ${fmt(usb.total)} total`;
      } else {
        el.textContent = `⚪ Internal Storage — ${fmt(internal.free)} free / ${fmt(internal.total)} total`;
      }
    })
    .catch(err => {
      console.error("[logs_panel] storage info error:", err);
      el.textContent = "Storage info unavailable.";
    });
}

function refreshLogs() {
  const loading = document.getElementById("logListLoading");
  const table = document.getElementById("logTable");
  const noLogs = document.getElementById("noLogsMsg");
  const body = document.getElementById("logTableBody");
  const pageInfo = document.getElementById("pageInfo");
  if (!loading || !table || !noLogs || !body || !pageInfo) return;

  // Show loading spinner; hide table & no-logs message explicitly
  loading.style.display = "";
  table.style.display = "none"; // ensure hidden while loading
  noLogs.style.display = "none"; // hide empty-state while fetching
  body.innerHTML = ""; // clear old rows

  safeFetch(`${API_PATHS?.logs?.list}?page=${currentPage}&page_size=${PAGE_SIZE}`)
    .then(r => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    })
    .then(data => {
      loading.style.display = "none";

      if (!data.ok || data.total === 0) {
        // Explicitly show the empty state; must override CSS display:none
        noLogs.style.display = "block";
        totalPages = 1;
        pageInfo.textContent = "Page 1 of 1";
        return;
      }

      // Safeguard: window.lastSSEPhase may be undefined if results_tab.js hasn't loaded yet
      const phase = (typeof window.lastSSEPhase === "string") ? window.lastSSEPhase : "IDLE";
      const isIdle = (phase === "IDLE" || phase === "ABORTED");

      data.files.forEach(entry => {
        const row = document.createElement("tr");

        // Row cells
        const nameTd = document.createElement("td");
        nameTd.textContent = entry.name;
        row.appendChild(nameTd);

        const sizeTd = document.createElement("td");
        sizeTd.textContent = humanFileSize(entry.size);
        row.appendChild(sizeTd);

        const getTd = document.createElement("td");
        const getLink = document.createElement("a");
        getLink.href = `${API_PATHS?.logs?.download}${entry.name}`;
        getLink.className = "btn btn-sm btn-outline-success";
        getLink.textContent = "Get";
        getLink.setAttribute("aria-label", `Download ${entry.name}`);
        getTd.appendChild(getLink);
        row.appendChild(getTd);

        const showTd = document.createElement("td");
        const showBtn = document.createElement("button");
        showBtn.className = "btn btn-sm btn-outline-primary";
        showBtn.textContent = "Show";
        showBtn.disabled = !isIdle;
        if (!isIdle) showBtn.title = "Disabled during live measurement";
        showBtn.onclick = () => window.chartLoadCSVSeries && chartLoadCSVSeries(entry.name);
        showBtn.setAttribute("aria-label", `Show ${entry.name} on chart`);
        showTd.appendChild(showBtn);
        row.appendChild(showTd);

        const delTd = document.createElement("td");
        const delBtn = document.createElement("button");
        delBtn.className = "btn btn-sm btn-outline-danger";
        delBtn.textContent = "X";
        delBtn.setAttribute("aria-label", `Delete ${entry.name}`);
        delBtn.onclick = () => deleteLog(entry.name);
        delTd.appendChild(delBtn);
        row.appendChild(delTd);

        body.appendChild(row);
      });

      // Explicitly override CSS rule (#logTable { display:none })
      table.style.display = "table"; // restore visibility

      totalPages = Math.max(1, Math.ceil(data.total / PAGE_SIZE));
      if (currentPage > totalPages) currentPage = totalPages; // clamp if total shrank
      pageInfo.textContent = `Page ${currentPage} of ${totalPages}`;

      const prevBtn = document.getElementById("prevPage");
      const nextBtn = document.getElementById("nextPage");
      const firstBtn = document.getElementById("firstPage");
      const lastBtn = document.getElementById("lastPage");
      if (prevBtn) prevBtn.disabled = (currentPage <= 1);
      if (nextBtn) nextBtn.disabled = (currentPage >= totalPages);
      if (firstBtn) firstBtn.disabled = (currentPage <= 1);
      if (lastBtn) lastBtn.disabled = (currentPage >= totalPages);
    })
    .catch(err => {
      loading.textContent = "Failed to load logs.";
      console.error("[logs_panel] refreshLogs error:", err);
    });
}

// Pagination buttons
// Pagination bindings moved into DOMContentLoaded for safety

// Delete file
function deleteLog(name) {
  window.showConfirmModal({
    title: "Delete Log File",
    message: `Are you sure you want to delete "${name}"? This action cannot be undone.`,
    confirmText: "Delete",
    confirmClass: "btn-danger",
    headerClass: "bg-danger-subtle",
    onConfirm: () => {
      safeFetch(`${API_PATHS?.logs?.delete}${encodeURIComponent(name)}`, { method: "DELETE" })
        .then(r => {
          if (!r.ok) throw new Error(`HTTP ${r.status}`);
          return r.json();
        })
        .then(data => {
          if (data.ok) {
            refreshLogs();
            refreshStorageInfo();
          } else {
            window.showConfirmModal({
              title: "Delete Failed",
              message: `Failed to delete file: ${data.error || "unknown error"}`,
              confirmText: "OK",
              cancelText: "",
              confirmClass: "btn-primary",
              headerClass: "bg-danger-subtle"
            });
          }
        })
        .catch(err => {
          window.showConfirmModal({
            title: "Delete Failed",
            message: "Error deleting file",
            confirmText: "OK",
            cancelText: "",
            confirmClass: "btn-primary",
            headerClass: "bg-danger-subtle"
          });
          console.error("[logs_panel] deleteLog error:", err);
        });
    }
  });
}

// File size formatting
function humanFileSize(bytes) {
  const n = Number(bytes);
  if (!Number.isFinite(n) || n <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"]; // future proof
  const i = Math.min(units.length - 1, Math.floor(Math.log10(n) / Math.log10(1024)));
  if (i === 0) return `${n} B`; // avoid decimals for raw bytes
  return (n / Math.pow(1024, i)).toFixed(1) + " " + units[i];
}
