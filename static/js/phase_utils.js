// ============================================================
// Phase Utilities – Phase constants and helpers
// ============================================================
// console.log("[phase_utils] loaded");

// ============================================================
// Phase Constants
// ============================================================
const PHASE = {
  IDLE: "IDLE",
  HOMING: "HOMING",
  MEASURING: "MEASURING",
  PAUSED: "PAUSED",
  SWITCHING: "SWITCHING",
  ABORTED: "ABORTED"
};

window.PHASE = PHASE;

// ============================================================
// Phase Helpers
// ============================================================

/**
 * Check if phase is active (measurement in progress)
 */
function isActivePhase(phase) {
  return phase === PHASE.MEASURING || phase === PHASE.PAUSED || 
         phase === PHASE.SWITCHING || phase === PHASE.HOMING;
}

/**
 * Check if phase allows jar selection
 */
function isSelectionPhase(phase) {
  return phase === PHASE.IDLE || phase === PHASE.ABORTED;
}

/**
 * Get human-readable phase name
 */
function getPhaseText(phase) {
  const phaseTexts = {
    [PHASE.IDLE]: "Ready",
    [PHASE.HOMING]: "Homing",
    [PHASE.MEASURING]: "Measuring",
    [PHASE.PAUSED]: "Paused",
    [PHASE.SWITCHING]: "Switching",
    [PHASE.ABORTED]: "Aborted"
  };
  return phaseTexts[phase] || "Unknown";
}

// Expose globally
window.isActivePhase = isActivePhase;
window.isSelectionPhase = isSelectionPhase;
window.getPhaseText = getPhaseText;
