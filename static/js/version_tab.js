let VM_CURRENT_SHORT = null;
let VM_SHOW_STABLE = true;

async function vm_fetchLocal() {
  try {
    const res = await safeFetch("/system/version/local");
    const data = await res.json();

    VM_CURRENT_SHORT = (data.BUILD_SHORT || "").trim();

    // --- build tag badge ---
    const tag = data.BUILD_TAG || "—";
    const tagBox = document.getElementById("vm-build-tag");

    if (tagBox) {
      if (tag && tag !== "—") {
        const isStable = tag.toLowerCase().startsWith("stable");
        const badgeClass = tag.startsWith("stable") ? "bg-success" :
          tag.startsWith("beta") ? "bg-warning text-dark" :
            "bg-secondary";
        tagBox.innerHTML = `<span class="badge ${badgeClass}">
          ⭐ ${tag}
        </span>`;
      } else {
        tagBox.innerHTML = `<span class="badge bg-light text-muted">no tag</span>`;
      }
    }

    // --- fill table ---
    const tbody = document.getElementById("vm-local-info");
    tbody.innerHTML = `
      <tr><th>Commit</th><td>${data.BUILD_SHORT || "?"}</td></tr>
      <tr><th>Date</th><td>${data.BUILD_DATE || "?"}</td></tr>
      <tr><th>Branch</th><td>${data.BUILD_BRANCH || "?"}</td></tr>
      <tr><th>Message</th><td>${data.BUILD_MESSAGE || ""}</td></tr>
    `;
  } catch (err) {
    console.error("vm_fetchLocal failed:", err);
  }
}

async function vm_fetchCommits(force = false) {
  const sel = document.getElementById("vm-commit-select");
  const btn = document.getElementById("vm-refresh-btn");
  const st = document.getElementById("vm-status");

  sel.innerHTML = `<option>Loading...</option>`;
  btn.disabled = true;
  st.textContent = "🔄 Fetching commits...";

  const url = `/system/version/github?${VM_SHOW_STABLE ? "stable=1&" : ""}${force ? "force=1" : ""}`;

  try {
    const res = await safeFetch(url);
    const data = await res.json();

    // populate dropdown
    sel.innerHTML = data.commits.map(c => {
      const current = VM_CURRENT_SHORT && VM_CURRENT_SHORT.startsWith(c.sha);
      const label = `${c.date} · ${c.sha} · ${c.message}${current ? " (current)" : ""}${c.stable ? " ⭐" : ""}`;
      return `<option value="${c.sha}" ${current ? "disabled" : ""}>${label}</option>`;
    }).join("");

    // update status
    const cached = data.cached;
    st.textContent = cached
      ? "⚠️ Using cached data — you can Force Refresh if needed."
      : "✅ Fresh data from GitHub (cache active ≈ 1 h).";

    btn.disabled = !cached;
    btn.className = `btn btn-sm ${cached ? "btn-outline-warning" : "btn-secondary"}`;

    if (!cached) vm_updateTimestamp();

  } catch (err) {
    console.warn("vm_fetchCommits failed:", err);
    st.textContent = `❌ Error fetching commits: ${err.message || err}`;
    btn.disabled = false;
  }
}

function vm_toggleStable() {
  VM_SHOW_STABLE = !VM_SHOW_STABLE;
  const btn = document.getElementById("vm-toggle-stable-btn");
  btn.textContent = VM_SHOW_STABLE ? "Show all commits" : "Show only stable";
  vm_fetchCommits(true);
}

function vm_updateTimestamp(save = true) {
  const el = document.getElementById("vm-last-update");
  const now = new Date();
  const formatted = now.toLocaleString(undefined, {
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit"
  });

  el.textContent = `🕓 Last updated: ${formatted}`;

  // ✅ persist timestamp in localStorage
  if (save) {
    localStorage.setItem("GaseraMux_LastUpdateTime", formatted);
  }
}

function vm_showSpinner(show) {
  const spinner = document.getElementById("vm-spinner");
  const icon = document.getElementById("vm-refresh-icon");
  if (show) {
    spinner.classList.remove("d-none");
    icon.classList.add("d-none");
  } else {
    spinner.classList.add("d-none");
    icon.classList.remove("d-none");
  }
}

async function vm_forceRefresh() {
  const st  = document.getElementById("vm-status");
  const sel = document.getElementById("vm-commit-select");
  const btn = document.getElementById("vm-refresh-btn");

  st.textContent = "🔄 Forcing fresh commit list...";
  btn.disabled = true;
  vm_showSpinner(true);

  try {
    // ✅ Respect current stable/all mode
    const url = `/system/version/github?${VM_SHOW_STABLE ? "stable=1&" : ""}force=1`;
    const res  = await safeFetch(url);
    const data = await res.json();

    // ✅ Rebuild dropdown
    sel.innerHTML = data.commits.map(c => {
      const current = VM_CURRENT_SHORT && VM_CURRENT_SHORT.startsWith(c.sha);
      const label = `${c.date} · ${c.sha} · ${c.message}${current ? " (current)" : ""}${c.stable ? " ⭐" : ""}`;
      return `<option value="${c.sha}" ${current ? "disabled" : ""}>${label}</option>`;
    }).join("");

    // ✅ Update status and button
    if (data.cached) {
      st.textContent = "⚠️ Using cached data — GitHub API limit reached or no new commits.";
      btn.disabled = false;
      btn.classList.remove("btn-secondary");
      btn.classList.add("btn-outline-warning");
    } else {
      st.textContent = "✅ Successfully fetched fresh data from GitHub.";
      btn.disabled = true;
      btn.classList.remove("btn-outline-warning");
      btn.classList.add("btn-secondary");
      vm_updateTimestamp();
    }

  } catch (err) {
    console.error("vm_forceRefresh error:", err);
    st.textContent = `❌ Error refreshing commits: ${err.message || err}`;
    btn.disabled = false;
  } finally {
    vm_showSpinner(false);
  }
}

async function vm_doCheckout() {
  const sha = document.getElementById("vm-commit-select").value;
  if (!sha) return alert("Select a commit first.");

  // Ignore same-commit switch
  if (VM_CURRENT_SHORT && VM_CURRENT_SHORT.startsWith(sha)) {
    document.getElementById("vm-status").textContent =
      `ℹ️ Already on ${sha}. No changes applied.`;
    return;
  }

  if (!confirm(`Switch to commit ${sha}? The service will restart.`)) return;

  const st = document.getElementById("vm-status");
  st.textContent = "⏳ Switching version...";

  try {
    const res = await safeFetch("/system/version/checkout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sha })
    });

    const data = await res.json();
    if (data.status === "ok") {
      st.textContent = `✅ Switched successfully to ${data.current.slice(0, 7)}.`;
      setTimeout(vm_fetchLocal, 4000);
    } else {
      st.textContent = `❌ Error: ${data.error || "unknown"}`;
    }
  } catch (err) {
    console.warn("Checkout failed:", err);
    st.textContent = "⚠️ Server restarting... Please refresh after a few seconds.";
  }
}

async function vm_doRollback() {
  if (!confirm("Rollback to previous version?")) return;
  const st = document.getElementById("vm-status");
  st.textContent = "⏳ Rolling back...";

  try {
    const res = await safeFetch("/system/version/rollback", { method: "POST" });
    const data = await res.json();
    if (data.status === "ok") {
      st.textContent = `✅ Rolled back to ${data.current.slice(0, 7)}.`;
      setTimeout(vm_fetchLocal, 4000);
    } else {
      st.textContent = `❌ Error: ${data.error || "unknown"}`;
    }
  } catch (err) {
    console.warn("Rollback failed:", err);
    st.textContent = "⚠️ Server restarting... Please refresh after a few seconds.";
  }
}

let VM_ADMIN_MODE = false;

function vm_setAdminVisible(show) {
  const card = document.getElementById("vm-admin-card");
  if (card) card.style.display = show ? "" : "none";
}

// Listen for secret combo: Ctrl + Shift + V
document.addEventListener("keydown", (ev) => {
  if (ev.ctrlKey && ev.shiftKey && ev.code === "KeyV") {
    VM_ADMIN_MODE = !VM_ADMIN_MODE;
    vm_setAdminVisible(VM_ADMIN_MODE);
    console.log(`Admin mode ${VM_ADMIN_MODE ? "enabled" : "disabled"}`);
    if (VM_ADMIN_MODE)
      alert("⚙️ Admin controls visible");
    else
      alert("🔒 Admin controls hidden");
  }
});

// Listen for tab changes
document.addEventListener('shown.bs.tab', (event) => {
  const newTarget = event.target.getAttribute('data-bs-target');
  if (newTarget !== '#tab-version') {
    VM_ADMIN_MODE = false;
    vm_setAdminVisible(false);
    console.log("Admin mode reset (switched tab)");
  }
});

// init
document.addEventListener("DOMContentLoaded", () => {
  // Restore last refresh time if available
  const savedTime = localStorage.getItem("GaseraMux_LastUpdateTime");
  if (savedTime) {
    const el = document.getElementById("vm-last-update");
    el.textContent = `🕓 Last updated: ${savedTime}`;
  }

  // Normal initialization
  if (document.getElementById("vm-local-info"))
    vm_fetchLocal().then(vm_fetchCommits);

  vm_setAdminVisible(false);

  document.getElementById("vm-checkout-btn").addEventListener("click", vm_doCheckout);
  document.getElementById("vm-rollback-btn").addEventListener("click", vm_doRollback);
  document.getElementById("vm-refresh-btn").addEventListener("click", vm_forceRefresh);
});

