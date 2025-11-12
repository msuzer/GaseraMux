// ============================================================
// Home Tab – Jar Visualization & Controls
// ============================================================
// console.log("[home_tab_visual] loaded");

const TOTAL_JARS = 31;
const jarGrid = document.getElementById("jarGrid");

// global running flag (controlled from core)
window.isMeasurementRunning = false;

// Create jars
for (let i = 1; i <= TOTAL_JARS; i++) {
    const j = document.createElement("div");
    j.className = "jar";
    j.dataset.id = i;
    j.innerHTML = `
    <div class="jar-neck"></div>
    <div class="jar-body"></div>
    <span class="jar-label">${i}</span>`;
    j.addEventListener("click", () => {
        // 🚫 prevent toggling while measurement running
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

// Apply a boolean mask (true = active) to all jars
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
// Reset transient states (called at new run or repeat)
// ------------------------------------------------------------
window.resetJarStates = function () {
    document.querySelectorAll(".jar").forEach(j =>
        j.classList.remove("sampling", "sampled")
    );
};

// ------------------------------------------------------------
// Phase-driven coloring / highlighting
// ------------------------------------------------------------
window.updateJarColors = function (ch, phase) {
    const jar = document.querySelector(`.jar[data-id="${ch + 1}"]`);
    if (!jar || !jar.classList.contains("active")) return;  // ✅ only active jars

    // remove sampling every phase first
    jar.classList.remove("sampling");

    if (phase === "MEASURING") {
        jar.classList.add("sampling");
    } else if (phase === "SWITCHING") {
        jar.classList.add("sampled");
    } else if (phase === "ABORTED" || phase === "IDLE") {
        
    }
};

// ------------------------------------------------------------
// Optional: grid lock visual cue
// ------------------------------------------------------------
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

// Selection buttons
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
        channelBadge.textContent = ch + 1;  // 1-based index
        channelCircle.dataset.phase = phase;
    }

    // window.highlightSamplingJar?.(ch + 1);
}

window.updateRepeatInfo = function (rep) {
    const totalRepeats = Number(document.getElementById("cfgRepeat").value) || 1;
    const currentRepeat = rep;
    const pct = (currentRepeat / totalRepeats) * 100;

    const circle = document.getElementById("repeatCircle");
    const text = document.getElementById("repeatText");

    // animate arc
    circle.setAttribute("stroke-dasharray", `${pct},100`);
    text.textContent = `${currentRepeat}/${totalRepeats}`;

    // dynamic color range for stroke
    let colorRange;
    if (pct <= 25) colorRange = "0-25";
    else if (pct <= 50) colorRange = "26-50";
    else if (pct <= 75) colorRange = "51-75";
    else colorRange = "76-100";

    circle.dataset.pct = colorRange;
};


window.updateCircularProgress = function (elId, textId, percent) {
    const circle = document.getElementById(elId);
    const text = document.getElementById(textId);
    const pct = Math.max(0, Math.min(100, percent || 0));

    // stroke animation
    circle.setAttribute("stroke-dasharray", `${pct},100`);
    text.textContent = `${pct}%`;

    // assign color range attribute for CSS hue shift
    let colorRange;
    if (pct <= 25) colorRange = "0-25";
    else if (pct <= 50) colorRange = "26-50";
    else if (pct <= 75) colorRange = "51-75";
    else colorRange = "76-100";

    circle.dataset.pct = colorRange;
}
