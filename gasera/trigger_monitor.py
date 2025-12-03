import time
import threading
from system.log_utils import verbose, info, warn, debug
from gpio.gpio_control import gpio
from gpio.pin_assignments import TRIGGER_PIN

class TriggerMonitor:
    """
    Monitors an active-low trigger input pin using libgpiod edge events.
    Converts short and long presses into Start / Abort actions.
    """

    DEBOUNCE_MS = 400
    LONG_PRESS_SEC = 4.0
    COOLDOWN_SEC = 1.0

    def __init__(self, engine):
        self.engine = engine
        self._last_action_time = 0.0
        self._press_start_time = None
        self._long_triggered = False
        self._stable_state = 1  # Active-low: released = 1
        self._lock = threading.Lock()
        self._started = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def start(self):
        if getattr(self, "_started", False):
            from system.log_utils import debug
            debug("[TRIGGER] Already started; skipping duplicate init")
            return
        try:
            info(f"[TRIGGER] Edge monitoring started on {TRIGGER_PIN}")
            gpio.watch(TRIGGER_PIN, self._on_edge, edge="both")
            self._started = True
        except OSError as e:
            if e.errno == 16:
                from system.log_utils import warn
                warn(f"[TRIGGER] GPIO already in use; skipping duplicate watcher")
            else:
                raise

    def stop(self):
        debug("[TRIGGER] No explicit stop needed for edge-based watcher")

    # ------------------------------------------------------------------
    # Event handler
    # ------------------------------------------------------------------
    def _on_edge(self, pin_name, val):
        now = time.time()
        with self._lock:
            # Validate value; libgpiod should provide 0/1
            try:
                val = 1 if int(val) != 0 else 0
            except Exception:
                warn(f"[TRIGGER] Invalid edge value: {val!r}")
                return
            # Debounce: ignore rapid bounces
            if (now - self._last_action_time) * 1000 < self.DEBOUNCE_MS:
                return

            # Cooldown: ignore repeated actions too quickly
            if now - self._last_action_time < self.COOLDOWN_SEC:
                debug("[TRIGGER] Ignored (cooldown active)")
                return

            # Update stable state
            self._stable_state = val
            if val == 0:
                self._on_press()
            else:
                self._on_release()

    # ------------------------------------------------------------------
    # Press / release logic
    # ------------------------------------------------------------------
    def _on_press(self):
        self._press_start_time = time.time()
        self._long_triggered = False
        verbose("[TRIGGER] Button pressed")

        # Start timer for long press
        t = threading.Timer(self.LONG_PRESS_SEC, self._fire_long_if_still_pressed)
        t.daemon = True
        t.start()
        self._long_timer = t

    def _on_release(self):
        now = time.time()
        verbose("[TRIGGER] Button released")

        # Cancel pending long press timer
        lt = getattr(self, "_long_timer", None)
        if lt and lt.is_alive():
            lt.cancel()

        # If not long triggered, treat as short press
        if self._press_start_time and not self._long_triggered:
            duration = now - self._press_start_time
            if duration < self.LONG_PRESS_SEC:
                self._handle_short_press()

        self._press_start_time = None
        self._last_action_time = now

    def _fire_long_if_still_pressed(self):
        with self._lock:
            if self._stable_state == 0 and self._press_start_time:
                self._handle_long_press()
                self._long_triggered = True
                self._press_start_time = None
                self._last_action_time = time.time()
                verbose("[TRIGGER] Long press triggered; waiting for release")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _handle_short_press(self):
        try:
            info("[TRIGGER] Short press → Start measurement")
            ok, msg = self.engine.start()
            if not ok:
                warn(f"[TRIGGER] Start rejected: {msg}")
        except Exception as e:
            warn(f"[TRIGGER] Start error: {e}")

    def _handle_long_press(self):
        if not self.engine.is_running():
            info("[TRIGGER] Long press ignored (no active measurement)")
            return
        try:
            info("[TRIGGER] Long press → Abort measurement")
            self.engine.stop()
        except Exception as e:
            warn(f"[TRIGGER] Abort error: {e}")
