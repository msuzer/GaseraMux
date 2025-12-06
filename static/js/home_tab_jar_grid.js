// ============================================================
// Home Tab – Jar Grid Management
// ============================================================
// Requires: home_tab_dom.js (for jarGrid)
// console.log("[home_tab_jar_grid] loaded");

const TOTAL_JARS = 31;

// ============================================================
// Jar Grid Creation
// ============================================================
(function createJarGrid() {
  for (let i = 1; i <= TOTAL_JARS; i++) {
    const jar = document.createElement("div");
    jar.className = "jar";
    jar.dataset.id = i;
    jar.innerHTML = `
        <div class="jar-neck"></div>
        <div class="jar-body"></div>
        <span class="jar-label">${i}</span>`;
    
    jar.addEventListener("click", () => {
      if (window.isMeasurementRunning) return;
      jar.classList.toggle("active");
      jar.classList.remove("sampled", "sampling");
    });
    
    jarGrid.appendChild(jar);
  }
})();

// ============================================================
// Jar Selection Utilities
// ============================================================
window.setAllJars = function (state) {
  document.querySelectorAll(".jar").forEach(jar => {
    jar.classList.toggle("active", state);
  });
};

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
};

window.getSelectedJars = function () {
  return Array.from(document.querySelectorAll(".jar.active"))
    .map(jar => Number(jar.dataset.id));
};

// ============================================================
// Jar State Management
// ============================================================
window.resetJarStates = function () {
  document.querySelectorAll(".jar").forEach(jar =>
    jar.classList.remove("sampling", "sampled")
  );
};

window.getLastEnabledJar = function () {
  const jarMask = window.getJarMask?.() ?? [];
  for (let i = jarMask.length - 1; i >= 0; i--) {
    if (jarMask[i]) return i;
  }
  return TOTAL_JARS - 1;
};

// ============================================================
// Jar Visual Updates
// ============================================================
window.updateJarColors = function (ch, phase) {
  const jar = document.querySelector(`.jar[data-id="${ch + 1}"]`);
  if (!jar || !jar.classList.contains("active")) return;

  // Remove transient states, preserve "sampled" for completed measurements
  jar.classList.remove("sampling", "paused");

  if (phase === window.PHASE.MEASURING) {
    jar.classList.remove("sampled");
    jar.classList.add("sampling");
  } else if (phase === window.PHASE.PAUSED) {
    jar.classList.remove("sampled");
    jar.classList.add("paused");
  } else if (phase === window.PHASE.SWITCHING) {
    jar.classList.add("sampled");
  } else if (phase === window.PHASE.ABORTED || phase === window.PHASE.IDLE) {
    // Keep sampled state intact for completed jars
  }
};
