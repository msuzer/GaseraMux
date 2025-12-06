// ============================================================
// Home Tab – Progress Circles & Grid Lock
// ============================================================
// Requires: home_tab_dom.js (for DOM elements cache)
// console.log("[home_tab_visual] loaded");

// ============================================================
// Selection Button Handlers
// ============================================================
btnAll.onclick = () => window.setAllJars?.(true);
btnNone.onclick = () => window.setAllJars?.(false);
btnInvert.onclick = () => window.invertJars?.();

// ============================================================
// Grid Lock Management
// ============================================================
window.updateGridLock = function () {
    const locked = window.isMeasurementRunning;

    jarGrid.classList.toggle("locked", locked);
    gridLockIcon.classList.toggle("bi-lock", locked);
    gridLockIcon.classList.toggle("bi-unlock", !locked);
    gridLockIcon.classList.toggle("locked", locked);
    gridLockIcon.classList.toggle("unlocked", !locked);
    gridLockIcon.title = locked ? "Grid locked during measurement" : "Grid unlocked";
    
    btnAll.disabled = locked;
    btnNone.disabled = locked;
    btnInvert.disabled = locked;
};

// ============================================================
// Progress Updaters
// ============================================================
window.updateChannelInfo = function (ch, phase) {
    if (channelBadge && channelCircle) {
        channelBadge.textContent = ch + 1;
        channelCircle.dataset.phase = phase;
    }
}

// Helper: Update any progress circle with percent and text
function updateProgressCircle(circleEl, textEl, percent, textContent) {
    const pct = Math.max(0, Math.min(100, percent || 0));

    circleEl.setAttribute("stroke-dasharray", `${pct},100`);
    textEl.textContent = textContent;

    // Color range for CSS styling
    let colorRange;
    if (pct <= 25) colorRange = "0-25";
    else if (pct <= 50) colorRange = "26-50";
    else if (pct <= 75) colorRange = "51-75";
    else colorRange = "76-100";

    circleEl.dataset.pct = colorRange;
}

window.updateRepeatInfo = function (rep, repeatTotal) {
    const total = repeatTotal || 0;
    const pct = (rep / total) * 100;
    updateProgressCircle(repCircle, repeatText, pct, `${rep}/${total}`);
};

window.updateCycleProgress = function (pct, stepIndex, enabledCount) {
    const total = enabledCount || 0;
    const completedInCycle = total > 0 ? (stepIndex % total) : 0;
    updateProgressCircle(runCircle, runPct, pct, `${completedInCycle}/${total}`);
};

window.updateCircularProgress = function (percent) {
    const pct = Math.max(0, Math.min(100, percent || 0));
    updateProgressCircle(overallCircle, overallPct, pct, `${pct}%`);
}
