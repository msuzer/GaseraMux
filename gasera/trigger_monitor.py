import time
import threading
from system.log_utils import info, warn, debug, error
from gpio.gpio_control import gpio
from gpio.pin_assignments import TRIGGER_PIN

class TriggerMonitor:
    """
    Monitors an active-low trigger input pin and converts presses into
    Start/Abort commands for the Gasera measurement engine.

    Features:
      • Active-low, edge-triggered logic
      • Short press (< LONG_PRESS_SEC) → Start
      • Long press  (≥ LONG_PRESS_SEC) → Abort
      • Debouncing and cooldown to prevent repeat triggers
      • Thread-safe, non-blocking, fully background operation
    """

    DEBOUNCE_MS = 750           # Debounce window for stable transitions
    POLL_MS = 250                # Sampling interval
    LONG_PRESS_SEC = 4.0        # Long-press threshold
    COOLDOWN_SEC = 2.0          # Ignore further presses for this period after action

    def __init__(self, engine):
        self.engine = engine
        self._stable_state = 1              # Active-low: 1 = released
        self._last_state_change = time.time()
        self._press_start_time = None
        self._last_action_time = 0.0
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._stop_event = threading.Event()
        self._started = False
    
    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self):
        if self._started:
            return
        info(f"[TRIGGER] Monitoring started on {TRIGGER_PIN}")
        self._thread.start()
        self._started = True

    def stop(self):
        self._stop_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout=1)
        info("[TRIGGER] Monitoring stopped")

    # ------------------------------------------------------------------
    # Internal loop
    # ------------------------------------------------------------------

    def _loop(self):
        """Main polling and debounce loop."""
        while not self._stop_event.is_set():
            now = time.time()

            try:
                raw = gpio.read(TRIGGER_PIN)
            except OSError as e:
                warn(f"[TRIGGER] GPIO busy error: {str(e)}")

            # Debounce detection
            if raw != self._stable_state:
                if (now - self._last_state_change) * 1000 >= self.DEBOUNCE_MS:
                    self._stable_state = raw
                    self._last_state_change = now
                    self._handle_edge(raw)
            else:
                self._last_state_change = now

            time.sleep(self.POLL_MS / 1000.0)

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------

    def _handle_edge(self, level: int):
        """Handle stable HIGH/LOW edges (after debouncing)."""
        # Active-low: 0 = pressed, 1 = released
        now = time.time()

        # Check cooldown
        if now - self._last_action_time < self.COOLDOWN_SEC:
            debug("[TRIGGER] Ignored (cooldown active)")
            return

        if level == 0:
            # Pressed
            self._press_start_time = now
            debug("[TRIGGER] Button pressed")
        else:
            # Released
            if self._press_start_time is None:
                return
            press_duration = now - self._press_start_time
            self._press_start_time = None
            if press_duration >= self.LONG_PRESS_SEC:
                self._handle_long_press()
            else:
                self._handle_short_press()
            self._last_action_time = now

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------

    def _handle_short_press(self):
        """Short press: start measurement if idle."""
        if self.engine.is_running():
            info("[TRIGGER] Short press ignored (engine already running)")
            return

        try:
            info("[TRIGGER] Short press → Start measurement")
            started = self.engine.start()
            if not started:
                warn("[TRIGGER] Engine refused to start (busy or misconfigured)")
        except Exception as e:
            warn(f"[TRIGGER] Start error: {e}")

    def _handle_long_press(self):
        """Long press: abort measurement if running."""
        if not self.engine.is_running():
            info("[TRIGGER] Long press ignored (no active measurement)")
            return

        try:
            info("[TRIGGER] Long press → Abort measurement")
            self.engine.stop()
        except Exception as e:
            warn(f"[TRIGGER] Abort error: {e}")

