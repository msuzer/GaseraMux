// ============================================================
// HOME TAB REFACTORING SUMMARY
// ============================================================
//
// BEFORE: Monolithic structure made it difficult to track code flow
// - home_tab_core.js: 337 lines (preferences + notifications + measurements)
// - home_tab_visual.js: 187 lines (jar creation + jar selection + progress circles)
//
// AFTER: Modular, focused files for easy navigation
//
// ============================================================
// FILE STRUCTURE & RESPONSIBILITIES
// ============================================================
//
// 1. home_tab_notifications.js (NEW)
//    - showAlert()
//    - showMeasurementSummaryToast()
//    Purpose: Centralized notification/toast handling
//
// 2. home_tab_jar_grid.js (NEW)
//    - createJarGrid() via IIFE
//    - setAllJars(), getJarMask(), applyJarMask(), invertJars()
//    - resetJarStates(), getLastEnabledJar()
//    - updateJarColors()
//    Purpose: All jar grid logic in one place
//
// 3. home_tab_preferences.js (NEW)
//    - collectPrefsData()
//    - loadPreferences()
//    - lockPreferenceInputs()
//    - initBuzzerToggle()
//    Purpose: Preference loading, saving, and input management
//
// 4. home_tab_visual.js (REFACTORED)
//    - Progress circles (channel, repeat, cycle, overall)
//    - Grid lock UI updates
//    - updateChannelInfo(), updateRepeatInfo(), updateCycleProgress(), updateCircularProgress()
//    - updateGridLock()
//    Purpose: Visual feedback and progress displays (no jar logic)
//
// 5. home_tab_core.js (REFACTORED)
//    - btnStart, btnAbort event handlers
//    - Countdown timer management
//    - applyPhase() - button states + input locking
//    - startMeasurement(), abortMeasurement()
//    - SSEHandler - measurement state tracking
//    Purpose: Measurement lifecycle control and SSE integration
//
// ============================================================
// LOAD ORDER (in index.html)
// ============================================================
//
// 1. core_index.js           - Global utilities (safeFetch, SSE hub, etc)
// 2. version_tab.js          - Version tab
// 3. home_tab_notifications  - Notification helpers
// 4. home_tab_jar_grid       - Jar grid creation & utilities
// 5. home_tab_preferences    - Preference management
// 6. home_tab_visual         - Progress displays & grid lock
// 7. home_tab_core           - Measurement control
//
// ============================================================
// CALL FLOWS
// ============================================================
//
// STARTUP:
//   DOMContentLoaded → home_tab_preferences.loadPreferences()
//   DOMContentLoaded → home_tab_core.applyPhase("IDLE")
//   DOMContentLoaded → home_tab_core.GaseraHub.subscribe(SSEHandler)
//
// JAR SELECTION:
//   User clicks jar → home_tab_jar_grid.jar.onclick
//   → toggles active class
//   → next loadPreferences calls applyJarMask()
//
// START MEASUREMENT:
//   User clicks start → home_tab_core.btnStart.onclick
//   → 5 second countdown
//   → startMeasurement()
//   → POST with collectPrefsData() from home_tab_preferences
//
// SSE UPDATE:
//   Backend sends phase/channel/progress
//   → home_tab_core.SSEHandler() processes
//   → applyPhase() updates buttons & locks inputs
//   → updateJarColors() updates jar display
//   → updateGridLock() locks/unlocks jar grid
//   → updateChannelInfo(), updateRepeatInfo(), etc update circles
//
// ============================================================
// KEY IMPROVEMENTS
// ============================================================
//
// ✓ Easier to navigate - each file has single responsibility
// ✓ Preferences logic isolated - easier to modify payment logic
// ✓ Jar grid logic isolated - easier to add/modify jar behavior
// ✓ Notifications centralized - consistent alert styling
// ✓ Visual updates focused - progress circles only
// ✓ Core control logic pure - measurement flow clearly visible
// ✓ Dependencies explicit - via window.* calls
// ✓ Less scrolling - smaller, focused files
//
// ============================================================
