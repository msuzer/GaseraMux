# Frontend Initialization Flow

## Overview

This document traces how the GaseraMux frontend initializes all UI components—textboxes, toggles, channel states, and measurements—from page load to the first SSE update.

## Load Order & Dependencies

### Script Loading Sequence (index.html)

```html
<!-- 1. Core utilities (load first) -->
<script src="/static/js/api_routes.js"></script>
<script src="/static/js/phase_utils.js"></script>

<!-- 2. Component modules -->
<script src="/static/js/home_tab_dom.js"></script>
<script src="/static/js/home_tab_notifications.js"></script>
<script src="/static/js/home_tab_jar_grid.js"></script>
<script src="/static/js/home_tab_preferences.js"></script>
<script src="/static/js/home_tab_visual.js"></script>
<script src="/static/js/home_tab_core.js"></script>

<!-- 3. Global coordination (load last) -->
<script src="/static/js/core_index.js"></script>
```

**Critical dependency order:**
1. `phase_utils.js` → Defines `window.PHASE` constants used everywhere
2. `home_tab_dom.js` → Caches DOM elements used by all modules
3. `home_tab_jar_grid.js` → Creates jar grid (runs immediately as IIFE)
4. Other modules → Register event handlers and functions
5. `core_index.js` → Starts SSE stream

## Initialization Phases

### Phase 1: Immediate Execution (Script Parse Time)

**Jar Grid Creation** (`home_tab_jar_grid.js` - IIFE)
```javascript
(function createJarGrid() {
  for (let i = 1; i <= TOTAL_JARS; i++) {
    const jar = document.createElement("div");
    jar.className = "jar";  // Default: inactive (gray)
    jar.dataset.id = i;
    // ... create DOM structure
    jarGrid.appendChild(jar);
  }
})();
```

**Result:** All 31 jars rendered in **inactive state** (no `.active` class)

### Phase 2: DOMContentLoaded Event

Multiple modules register `DOMContentLoaded` handlers that execute in parallel:

#### 2.1 Load Preferences (`home_tab_preferences.js:85`)

```javascript
document.addEventListener("DOMContentLoaded", () => {
  loadPreferences();  // ← Fetches from backend
  initBuzzerToggle();
});
```

**`loadPreferences()` Flow:**
1. Fetches `/system/api/settings/read` (GET)
2. Receives backend preferences:
   ```json
   {
     "measurement_duration": 300,
     "pause_seconds": 5,
     "repeat_count": 1,
     "include_channels": [true, false, true, ...],  // 31-element boolean array
     "online_mode_enabled": true,
     "buzzer_enabled": true
   }
   ```
3. Updates UI elements:
   ```javascript
   measureInput.value = p.measurement_duration ?? 300;
   pauseInput.value = p.pause_seconds ?? 5;
   repeatInput.value = p.repeat_count ?? 1;
   buzzerToggle.checked = p.buzzer_enabled ?? true;
   onlineModeToggle.checked = p.online_mode_enabled ?? true;
   ```
4. **Applies jar mask** (critical step):
   ```javascript
   window.applyJarMask?.(p.include_channels ?? []);
   ```

**`applyJarMask()` Implementation:**
```javascript
window.applyJarMask = function (mask = []) {
  const jars = document.querySelectorAll(".jar");
  jars.forEach((jar, i) => {
    jar.classList.toggle("active", !!mask[i]);  // ← Restores saved state
  });
};
```

**Result:** Textboxes, toggles, and jar states restored from backend preferences

#### 2.2 Initialize Core Measurement Logic (`home_tab_core.js:271`)

```javascript
document.addEventListener("DOMContentLoaded", () => {
  window.loadPreferences?.();  // Redundant, already called by preferences module
  applyPhase(window.PHASE.IDLE);  // ← Set initial phase
  window.GaseraHub?.subscribe(SSEHandler);  // ← Subscribe to SSE updates
});
```

**`applyPhase(PHASE.IDLE)` Flow:**
```javascript
function applyPhase(phase) {
  const isRunning = window.isActivePhase(phase);  // false for IDLE
  
  // Reset start button
  btnStart.textContent = "Start Measurement";
  btnStart.classList.add("btn-success");
  btnStart.disabled = false;  // ← Enabled for user interaction
  
  // Disable abort button (nothing to abort)
  btnAbort.disabled = true;
  
  // Unlock preference inputs
  window.lockPreferenceInputs?.(false);  // ← Inputs become editable
}
```

**Result:** Buttons in correct initial state, inputs unlocked

#### 2.3 Start SSE Stream (`core_index.js:287`)

```javascript
document.addEventListener("DOMContentLoaded", () => {
  const resultsTab = document.querySelector("#results-tab");
  resultsTab?.addEventListener("shown.bs.tab", () => {
    window.liveChart?.resize?.();
  });
  
  startGaseraSSE();  // ← Opens SSE connection
});
```

**`startGaseraSSE()` Flow:**
```javascript
function startGaseraSSE() {
  window.gaseraSSE = new EventSource(API_PATHS?.measurement?.events);
  
  window.gaseraSSE.onmessage = e => {
    const data = JSON.parse(e.data || "{}");
    window.GaseraHub.emit(data);  // ← Broadcasts to all subscribers
  };
  
  window.gaseraSSE.onerror = () => {
    console.warn("[SSE] lost connection, retrying...");
    setTimeout(startGaseraSSE, 5000);
  };
}
```

**Result:** SSE connection established, ready to receive backend state

### Phase 3: First SSE Message Reception

Backend sends initial state snapshot immediately upon connection:

```json
{
  "phase": "IDLE",
  "current_channel": 0,
  "next_channel": null,
  "percent": 0,
  "overall_percent": 0,
  "repeat_index": 0,
  "repeat_total": 0,
  "enabled_count": 0,
  "step_index": 0,
  "total_steps": 0,
  "elapsed_seconds": 0.0,
  "tt_seconds": null,
  "connection": {
    "online": true  // ← Gasera connection status
  },
  "live_data": {}
}
```

**SSE Handler Processing** (`home_tab_core.js:SSEHandler`)

```javascript
function SSEHandler(d) {
  const newPhase = d.phase ?? window.PHASE.IDLE;
  const ch = d.current_channel ?? 0;
  
  // First-time initialization checks
  const phaseChanged = currentPhase !== newPhase;  // true on first SSE
  
  if (phaseChanged) {
    applyPhase(newPhase);  // ← Redundant for IDLE, but ensures sync
    window.updateJarColors?.(ch, newPhase);
    window.isMeasurementRunning = window.isActivePhase(newPhase);  // false
    window.updateGridLock?.();  // Unlock jar grid
    currentPhase = newPhase;
  }
  
  // Update progress circles (even at 0%)
  window.updateRepeatInfo?.(d.repeat_index, d.repeat_total);
  window.updateCycleProgress?.(d.percent, d.step_index, d.enabled_count);
  window.updateCircularProgress?.(d.overall_percent);
  
  // Update connection footer
  window.updateFooterStatus?.(d.connection?.online);
}
```

**Result:** UI synchronized with backend state, connection status confirmed

## Component-by-Component Initialization

### Textboxes (Measurement Settings)

| Element | ID | Default | Restored From | When |
|---------|-----|---------|---------------|------|
| Measurement Duration | `measureInput` | 300 | `/system/api/settings/read` | DOMContentLoaded |
| Pause Seconds | `pauseInput` | 5 | `/system/api/settings/read` | DOMContentLoaded |
| Repeat Count | `repeatInput` | 1 | `/system/api/settings/read` | DOMContentLoaded |

**Initial State:** Unlocked (editable), populated from backend preferences

### Toggle Switches

| Element | ID | Default | Restored From | When |
|---------|-----|---------|---------------|------|
| Buzzer | `buzzerToggle` | `true` | `/system/api/settings/read` | DOMContentLoaded |
| Online Mode | `onlineModeToggle` | `true` | `/system/api/settings/read` | DOMContentLoaded |

**Initial State:** Checked/unchecked based on backend state

### Channel States (Jar Grid)

**Initialization Sequence:**

1. **Script Parse Time:** 31 jars created, all **inactive** (gray)
   ```html
   <div class="jar" data-id="1">
     <!-- No .active class = gray/inactive -->
   </div>
   ```

2. **DOMContentLoaded → loadPreferences():** Applies saved selection mask
   ```javascript
   applyJarMask([true, false, true, ...]);
   // Adds .active class to selected jars → turns green
   ```

3. **First SSE Message:** Confirms no measurement running
   ```javascript
   window.isMeasurementRunning = false;  // Grid remains unlocked
   ```

**Visual States:**
- **Gray (default):** `.jar` (no classes) - not selected
- **Green (active):** `.jar.active` - selected for measurement
- **Blue (measuring):** `.jar.active.sampling` - currently measuring
- **Orange (paused):** `.jar.active.paused` - pause before measurement
- **Purple (sampled):** `.jar.active.sampled` - measurement complete

**Initial State:** Green (active) for channels restored from preferences, gray for others

### Buttons

| Button | ID | Initial Text | Initial State | Initial Class |
|--------|-----|--------------|---------------|---------------|
| Start | `btnStart` | "Start Measurement" | Enabled | `btn-success` (green) |
| Abort | `btnAbort` | "Abort Measurement" | Disabled | `btn-danger` (red) |

**Applied by:** `applyPhase(PHASE.IDLE)` in DOMContentLoaded

### Progress Circles

| Circle | Purpose | Initial Value | Updated By |
|--------|---------|---------------|------------|
| Circular Progress | Overall measurement progress | 0% | First SSE message |
| Cycle Progress | Current repeat cycle progress | "0/0 steps" | First SSE message |
| Repeat Info | Repeat counter | "Repeat 1/0" | First SSE message |

**Initial State:** All at zero/empty, updated by first SSE message

### Footer Status

| Element | ID | Initial State | Source |
|---------|-----|---------------|--------|
| Connection Icon | `connIcon` | `bi-wifi` or `bi-wifi-off` | First SSE `connection.online` |
| Connection Text | `connStatus` | "Gasera Online" or "Gasera Offline" | First SSE `connection.online` |
| Timer Display | `etttDisplay` | "00:00 / 00:00" | Updated during measurement only |

**Initial State:** Set by first SSE message's `connection` field

## Timeline Summary

| Time | Event | Action | Result |
|------|-------|--------|--------|
| T+0ms | **Script parse** | Jar grid IIFE creates 31 jars | All jars gray (inactive) |
| T+0ms | **Script parse** | Functions/handlers registered | Ready for DOMContentLoaded |
| T+~50ms | **DOMContentLoaded** | `loadPreferences()` fires | Fetches backend settings |
| T+~50ms | **DOMContentLoaded** | `applyPhase(IDLE)` fires | Buttons/inputs initialized |
| T+~50ms | **DOMContentLoaded** | `startGaseraSSE()` fires | SSE connection opens |
| T+~100ms | **HTTP Response** | Preferences received | Textboxes/toggles populated |
| T+~100ms | **HTTP Response** | `applyJarMask()` called | Jar states restored (green) |
| T+~150ms | **SSE First Message** | Backend state received | UI synced with backend |
| T+~150ms | **SSE Handler** | `SSEHandler()` processes | Progress/footer updated |
| T+200ms | **Initialization Complete** | All components synchronized | UI ready for interaction |

## Key Design Patterns

### 1. Defensive Defaults
All components have sensible defaults in case backend fetch fails:
```javascript
measureInput.value = p.measurement_duration ?? 300;  // Fallback to 300
pauseInput.value = p.pause_seconds ?? 5;             // Fallback to 5
```

### 2. Idempotent Updates
Functions can be called multiple times safely:
```javascript
applyPhase(window.PHASE.IDLE);  // Called twice: DOMContentLoaded + first SSE
// No side effects from duplicate calls
```

### 3. Optional Chaining for Modularity
Functions check existence before calling:
```javascript
window.loadPreferences?.();      // Won't crash if module not loaded
window.updateJarColors?.(ch, phase);
```

### 4. State Synchronization Priority
1. **Backend preferences** (GET `/system/api/settings/read`) → Primary source of truth for settings
2. **SSE state** (GET `/gasera/api/measurement/events`) → Primary source of truth for measurement state
3. **Local UI state** → Transient, always overwritten by backend

### 5. Lazy Evaluation
Components only initialize what's visible/needed:
```javascript
// Timer display starts hidden, only shown during measurement
if (window.isActivePhase(newPhase)) {
  window.updateETTTDisplay?.();
}
```

## Potential Race Conditions (All Handled)

### Race 1: Preferences vs. First SSE
**Scenario:** SSE arrives before preference HTTP response  
**Handling:** Both are idempotent, final state correct regardless of order

### Race 2: Multiple DOMContentLoaded Handlers
**Scenario:** Load order of handlers unpredictable  
**Handling:** All handlers independent, no shared mutable state

### Race 3: User Interaction Before Init Complete
**Scenario:** User clicks jar before `applyJarMask()` completes  
**Handling:** Jars work with or without backend state, backend becomes source of truth on next save

## Debugging Tips

### Check Initialization State

**In browser console:**
```javascript
// Check if SSE connected
window.gaseraSSE.readyState  // 1 = OPEN, 0 = CONNECTING, 2 = CLOSED

// Check current phase
btnStart.dataset.phase  // Should be empty string or "IDLE" after init

// Check jar states
window.getJarMask()  // Returns array of 31 booleans

// Check preference values
measureInput.value  // Should match backend
pauseInput.value
repeatInput.value

// Check SSE handler registered
window.GaseraHub.callbacks.size  // Should be > 0
```

### Network Activity

**Expected requests during initialization:**
1. `GET /system/api/settings/read` - Fetch preferences
2. `GET /gasera/api/measurement/events` - Open SSE stream (stays open)

**Response times:**
- Preferences: <50ms typical
- SSE connection: <100ms to first message

### Visual Indicators

**Correct initialization:**
- ✅ Jars show green for selected channels (not all gray)
- ✅ "Start Measurement" button is green and enabled
- ✅ "Abort Measurement" button is disabled
- ✅ Textboxes contain non-zero values
- ✅ Footer shows connection status (online/offline)
- ✅ No console errors about missing elements

**Incorrect initialization:**
- ❌ All jars gray (preferences not loaded)
- ❌ Start button disabled (SSE not synced)
- ❌ Textboxes empty or showing defaults (HTTP fetch failed)
- ❌ Footer showing "00:00 / 00:00" without connection icon (SSE not connected)

## Related Documentation

- [Home Tab Architecture](../static/js/HOME_TAB_ARCHITECTURE.md) - Module structure and dependencies
- [SSE Data Flow](7_sse_data_flow_analysis.md) - Real-time state updates after initialization
- [Phase Handling](../static/js/phase_utils.js) - Phase constants and utilities

---

**Document Version:** 1.0  
**Last Updated:** December 4, 2025  
**Author:** GitHub Copilot (Claude Sonnet 4.5)
