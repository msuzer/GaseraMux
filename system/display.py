import time
import socket
import subprocess
import threading
from datetime import datetime
from dataclasses import dataclass
from typing import Optional
from gasera.controller import gasera # for connection check
from .log_utils import debug, warn
from .display_driver import DisplayDriver

display = DisplayDriver()

@dataclass
class MeasurementState:
    """Container for measurement display state."""
    state: str = "idle"          # "idle" | "run" | "done"
    phase: str = "IDLE"
    channel: int = 0
    repeat: int = 0
    repeat_total: int = 0
    step: int = 0                # current overall step number
    total_steps: int = 0         # total steps (repeat_count × enabled_count)
    tt_seconds: Optional[float] = None
    start_time: Optional[float] = None
    stop_time: Optional[float] = None
    aborted: bool = False

    def elapsed_time(self) -> Optional[float]:
        """Return elapsed seconds from start_time to now (or stop_time if done)."""
        if not self.start_time:
            return None
        end = self.stop_time if self.stop_time else time.time()
        return end - self.start_time

    def reset_timing(self):
        """Clear timing fields for fresh run."""
        self.start_time = None
        self.stop_time = None
        self.tt_seconds = None

    def is_running(self) -> bool:
        """Check if measurement is actively running."""
        return self.state == "run"

    def is_done(self) -> bool:
        """Check if measurement completed or aborted."""
        return self.state == "done"

    def mark_started(self):
        """Mark measurement start with current timestamp."""
        self.state = "run"
        self.start_time = time.time()
        self.stop_time = None
        self.aborted = False

    def mark_completed(self, aborted: bool = False):
        """Mark measurement completion with current timestamp."""
        self.state = "done"
        self.stop_time = time.time()
        self.aborted = aborted

    def return_to_idle(self):
        """Reset to idle state and clear timing."""
        self.state = "idle"
        self.start_time = None
        self.stop_time = None
        self.aborted = False

# Global display state instance
display_info = MeasurementState()

# === Helpers ===
def format_duration(seconds, fixed=False):
    """Format seconds as duration.
    - If fixed=False: MM:SS for <1h, HH:MM:SS for >=1h
    - If fixed=True: always HH:MM:SS
    """
    if not isinstance(seconds, (int, float)) or seconds < 0:
        return "--:--"
    elapsed = int(seconds)
    hours = elapsed // 3600
    minutes = (elapsed % 3600) // 60
    secs = elapsed % 60
    if fixed or hours > 0:
        return f"{hours:02}:{minutes:02}:{secs:02}"
    return f"{minutes:02}:{secs:02}"

def format_consistent_pair(et_seconds, tt_seconds, fixed=False):
    """
    Return (et_str, tt_str) formatted consistently.
    - If fixed=True: both use HH:MM:SS
    - If fixed=False: choose HH:MM:SS if either has hours, else MM:SS for both
    """
    et = et_seconds if isinstance(et_seconds, (int, float)) and et_seconds >= 0 else None
    tt = tt_seconds if isinstance(tt_seconds, (int, float)) and tt_seconds >= 0 else None

    if fixed:
        return (
            format_duration(et, fixed=True) if et is not None else "--:--",
            format_duration(tt, fixed=True) if tt is not None else "--:--",
        )

    # dynamic: if any shows hours, both render as HH:MM:SS
    show_hours = (et or 0) >= 3600 or (tt or 0) >= 3600
    if show_hours:
        return (
            format_duration(et, fixed=True) if et is not None else "--:--",
            format_duration(tt, fixed=True) if tt is not None else "--:--",
        )
    else:
        return (
            format_duration(et, fixed=False) if et is not None else "--:--",
            format_duration(tt, fixed=False) if tt is not None else "--:--",
        )

def get_ip_address():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "0.0.0.0"

def get_wifi_ssid():
    try:
        ssid = subprocess.check_output(["iwgetid", "-r"], text=True).strip()
        return ssid if ssid else "No WiFi"
    except Exception:
        return "Unknown"

def get_gasera_status():
    try:
        return "Online" if gasera.is_connected() else "Offline"
    except Exception:
        return "Unknown"

# === Layouts ===
def draw_idle():
    ssid = get_wifi_ssid()
    ip = get_ip_address()
    gasera_status = get_gasera_status()
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    display.draw_text_lines([
        f"W: {ssid}",
        f"IP: {ip}",
        f"G: Gasera {gasera_status}",
        f"T: {now}",
    ])

def draw_run():
    """Show measurement info with live elapsed time and IP."""
    # Calculate and format elapsed time
    et_val = display_info.elapsed_time()
    et_str, tt_str = format_consistent_pair(et_val, display_info.tt_seconds, fixed=False)
    ip = get_ip_address() or "no IP"

    display.draw_text_lines([
        f"> {display_info.phase}",
        f"Ch{display_info.channel}  Step {display_info.step}/{display_info.total_steps}",
        f"D: {et_str}/{tt_str}",
        f"IP: {ip}",
    ])

def draw_done():
    """Display concise completion summary with duration and timestamp."""
    et_val = display_info.elapsed_time()
    et_str, tt_str = format_consistent_pair(et_val, display_info.tt_seconds, fixed=False)
    now = datetime.now().strftime("%d.%m.%Y %H:%M")

    title = "ABORTED..." if display_info.aborted else "MEASUREMENT DONE"
    
    # Show completed steps:
    # - If completed normally, all steps done
    # - If aborted during SWITCHING, that measurement was completed (step done)
    # - If aborted during PAUSED/MEASURING, that step was not completed (step-1)
    if display_info.aborted:
        # SWITCHING means measurement done, just switching to next
        if display_info.phase == "SWITCHING":
            completed_steps = display_info.step  # current step was completed
        else:
            completed_steps = max(0, display_info.step - 1)  # current step not completed
    else:
        completed_steps = display_info.total_steps  # all done
        
    steps_display = f"{completed_steps}/{display_info.total_steps}"

    display.draw_text_lines([
        title,
        f"Done: {steps_display} steps",
        f"D: {et_str}/{tt_str}",
        f"T: {now}",
    ])

# === OLED updater thread ===
def display_updater():
    """
    Background worker that refreshes the display every second
    for OLED or HD44780 character LCD. Auto-detects hardware
    via DisplayDriver (0x3C → OLED, 0x3F → LCD).
    """
    if not (display.oled or display.lcd):
        warn("[DISPLAY] no display found on I²C3, skipping updates.")
        return

    last_state = None
    last_idle_refresh = 0

    while True:
        state = display_info.state

        # Log state transitions
        if state != last_state:
            debug(f"[DISPLAY] state change: {last_state or '—'} → {state} @ {time.strftime('%H:%M:%S')}")

        if state == "run":
            draw_run()

        elif state == "done":
            # Draw only once when switching into "done"
            if last_state != "done":
                draw_done()

        elif state == "idle":
            now = time.time()
            if now - last_idle_refresh >= 10.0 or last_state != "idle":
                draw_idle()
                last_idle_refresh = now

        else:
            # Unknown state, do nothing
            time.sleep(1.0)
            continue

        last_state = state
        time.sleep(1.0)

# === External API ===
def update_measurement_state(state: MeasurementState):
    """Convenience helper called from measurement thread."""
    # Mark start time on first call when measurement begins
    if display_info.start_time is None:
        display_info.mark_started()
    else:
        display_info.state = "run"

    display_info.phase = state.phase
    display_info.channel = state.channel
    display_info.repeat = state.repeat
    display_info.repeat_total = state.repeat_total
    display_info.step = state.step
    display_info.total_steps = state.total_steps
    display_info.tt_seconds = state.tt_seconds

def show_run_complete(aborted: bool = False):
    """Display the completion summary on the OLED.
    Calculates actual duration from start_time to now.
    If aborted is True, marks the run as aborted."""
    display_info.mark_completed(aborted)

    # Background worker to revert display after timeout
    def _revert_to_idle():
        time.sleep(10)
        display_info.return_to_idle()

    threading.Thread(target=_revert_to_idle, daemon=True).start()

def start_display_thread():
    t = threading.Thread(target=display_updater, daemon=True, name="display-updater")
    t.start()
