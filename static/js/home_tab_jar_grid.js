// ============================================================
// Home Tab – Jar Grid Management
// ============================================================
// Requires: home_tab_dom.js (for jarGrid)
// console.log("[home_tab_jar_grid] loaded");

const TOTAL_JARS = 31;

// Channel state constants (matches backend ChannelState)
const ChannelState = {
  INACTIVE: 0,
  ACTIVE: 1,
  SAMPLED: 2
};

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
      
      if (jar.classList.contains("active")) {
        jar.classList.remove("active");
        if (jar.classList.contains("sampled")) {
          jar.classList.remove("sampled");
          jar.dataset.wasSampled = "true";
        }
      } else {
        jar.classList.add("active");
        if (jar.dataset.wasSampled === "true") {
          jar.classList.add("sampled");
          jar.dataset.wasSampled = "false";
        }
      }

      if (jar.classList.contains("sampling")) {
        jar.classList.remove("sampling");
      }
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

// Line 43-45, update getJarMask to return state 2 for sampled jars
window.getJarMask = function () {
  return Array.from(document.querySelectorAll(".jar"))
    .map(j => {
      if (j.classList.contains("sampled")) return ChannelState.SAMPLED;
      return j.classList.contains("active") ? ChannelState.ACTIVE : ChannelState.INACTIVE;
    });
};

window.applyJarMask = function (mask = []) {
  const jars = document.querySelectorAll(".jar");
  jars.forEach((jar, i) => {
    const state = mask[i];

    if (state === ChannelState.INACTIVE)  {
      jar.classList.remove("active", "sampled");
    } else {
      jar.classList.add("active");
      if (state === ChannelState.SAMPLED) {
        jar.classList.add("sampled");
      } else {
        jar.classList.remove("sampled");
      }
    }
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
