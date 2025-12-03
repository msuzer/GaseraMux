// ============================================================
// Home Tab – Jar Visualization & Controls
// ============================================================
// console.log("[home_tab_visual] loaded");

const TOTAL_JARS = 31;
const jarGrid = document.getElementById("jarGrid");

window.isMeasurementRunning = false;

// ============================================================
// Jar Grid Creation
// ============================================================
for (let i = 1; i <= TOTAL_JARS; i++) {
    const j = document.createElement("div");
    j.className = "jar";
    j.dataset.id = i;
    j.innerHTML = `
        <div class="jar-neck"></div>
        <div class="jar-body"></div>
        <span class="jar-label">${i}</span>`;
    j.addEventListener("click", () => {
        if (window.isMeasurementRunning) return;
        j.classList.toggle("active");
        j.classList.remove("sampled", "sampling");
    });
    jarGrid.appendChild(j);
}


// Utility helpers
window.setAllJars = function (state) {
    document.querySelectorAll(".jar").forEach(jar => {
        jar.classList.toggle("active", state);
    });
}

window.getJarMask = function () {
    return Array.from(document.querySelectorAll(".jar"))
        .map(j => j.classList.contains("active"));
};

window.applyJarMask = function (mask = []) {
    const jars = document.querySelectorAll(".jar");
    jars.forEach((jar, i) => {
        jar.classList.toggle("active", !!mask[i]);
    });
};

window.invertJars = function () {
    document.querySelectorAll(".jar").forEach(jar => {
        jar.classList.toggle("active");
    });
}

// Optional: highlight currently sampled jar
window.highlightSamplingJar = function (id) {
    document.querySelectorAll(".jar").forEach(jar => {
        jar.classList.remove("sampling");
        if (Number(jar.dataset.id) === id) jar.classList.add("sampling");
    });
}

// Optional: get currently selected jars
window.getSelectedJars = function () {
    return Array.from(document.querySelectorAll(".jar.active"))
        .map(jar => Number(jar.dataset.id));
}

// ------------------------------------------------------------
// Jar State Management
// ------------------------------------------------------------
window.resetJarStates = function () {
    document.querySelectorAll(".jar").forEach(j =>
        j.classList.remove("sampling", "sampled")
    );
};

window.getLastEnabledJar = function () {
    const jarMask = window.getJarMask?.() ?? [];
    for (let i = jarMask.length - 1; i >= 0; i--) {
        if (jarMask[i]) {
            return i;
        }
    }
    return TOTAL_JARS - 1;
};

window.updateJarColors = function (ch, phase) {
    const jar = document.querySelector(`.jar[data-id="${ch + 1}"]`);
    if (!jar || !jar.classList.contains("active")) return;

    // Remove transient states, preserve "sampled" for completed measurements
    jar.classList.remove("sampling", "paused");

    if (phase === "MEASURING") {
        jar.classList.remove("sampled");
        jar.classList.add("sampling");
    } else if (phase === "PAUSED") {
        jar.classList.remove("sampled");
        jar.classList.add("paused");
    } else if (phase === "SWITCHING") {
        jar.classList.add("sampled");
    } else if (phase === "ABORTED" || phase === "IDLE") {
        // Keep sampled state intact for completed jars
    }
};

// ============================================================
// Grid Lock Visual
// ============================================================
window.updateGridLock = function () {
  const grid = document.getElementById("jarGrid");
  const icon = document.getElementById("gridLockIcon");
  const locked = window.isMeasurementRunning;

  if (locked) {
    grid.classList.add("locked");
    icon.classList.remove("bi-unlock", "unlocked");
    icon.classList.add("bi-lock", "locked");
    icon.title = "Grid locked during measurement";
  } else {
    grid.classList.remove("locked");
    icon.classList.remove("bi-lock", "locked");
    icon.classList.add("bi-unlock", "unlocked");
    icon.title = "Grid unlocked";
  }
};

// ============================================================
// Selection Button Handlers
// ============================================================
document.getElementById("btnAll").onclick = () => setAllJars(true);
document.getElementById("btnNone").onclick = () => setAllJars(false);
document.getElementById("btnInvert").onclick = () => invertJars();

// ============================================================
// Progress Updaters
// ============================================================
const channelBadge = document.getElementById("channelBadge");
const channelCircle = document.getElementById("channelCircle");
const repeatInfo = document.getElementById("repeatInfo");
const repCircle = document.getElementById("repeatCircle");

window.updateChannelInfo = function (ch, phase) {
    if (channelBadge && channelCircle) {
        channelBadge.textContent = ch + 1;
        channelCircle.dataset.phase = phase;
    }
}

// Helper: Update any progress circle with percent and text
function updateProgressCircle(elId, textId, percent, textContent) {
    const circle = document.getElementById(elId);
    const text = document.getElementById(textId);
    const pct = Math.max(0, Math.min(100, percent || 0));

    circle.setAttribute("stroke-dasharray", `${pct},100`);
    text.textContent = textContent;

    // Color range for CSS styling
    let colorRange;
    if (pct <= 25) colorRange = "0-25";
    else if (pct <= 50) colorRange = "26-50";
    else if (pct <= 75) colorRange = "51-75";
    else colorRange = "76-100";

    circle.dataset.pct = colorRange;
}

window.updateRepeatInfo = function (rep, repeatTotal) {
    const total = repeatTotal || 0;
    const pct = (rep / total) * 100;
    updateProgressCircle("repeatCircle", "repeatText", pct, `${rep}/${total}`);
};

window.updateCycleProgress = function (pct, stepIndex, enabledCount) {
    const total = enabledCount || 0;
    const completedInCycle = total > 0 ? (stepIndex % total) : 0;
    updateProgressCircle("runCircle", "runPct", pct, `${completedInCycle}/${total}`);
};

window.updateCircularProgress = function (percent) {
    const pct = Math.max(0, Math.min(100, percent || 0));
    updateProgressCircle("overallCircle", "overallPct", pct, `${pct}%`);
}
