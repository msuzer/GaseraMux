import time
import socket
import subprocess
import threading
from datetime import datetime
from gasera.controller import gasera # for connection check
from .log_utils import debug, info, warn
from .display_driver import DisplayDriver

display = DisplayDriver()

display_info = {
    "state": "idle",          # "idle" | "run" | "done"
    "phase": "IDLE",
    "channel": 0,
    "total": 0,
    "repeat": 0,
    "repeat_total": 0,
    "start_time": None,
    "stop_time": None,
    "duration": None,
    "aborted": False
}

# === Helpers ===
def get_ip_address(ifname="wlan0"):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
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
    ssid = get_wifi_ssid() or "-"
    ip = get_ip_address("wlan0") or "no IP"
    gasera_status = get_gasera_status() or "OFFLINE"
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    display.draw_text_lines([
        f"W: {ssid}",
        f"IP: {ip}",
        f"G: Gasera {gasera_status}",
        f"T: {now}",
    ])

def draw_run():
    """Show measurement info with live elapsed time and IP."""
    phase = display_info.get("phase", "MEASURING")
    ch = display_info.get("channel", 0)
    total = display_info.get("total", 0)
    rep = display_info.get("repeat", 0)
    rep_total = display_info.get("repeat_total", 0)
    start_time = display_info.get("start_time")

    # Format elapsed time (MM:SS or HH:MM:SS)
    if start_time:
        elapsed = int(time.time() - start_time)
        hours = elapsed // 3600
        minutes = (elapsed % 3600) // 60
        seconds = elapsed % 60
        if hours > 0:
            et_str = f"{hours:02}:{minutes:02}:{seconds:02}"
        else:
            et_str = f"{minutes:02}:{seconds:02}"
    else:
        et_str = "--:--"

    ip = get_ip_address("wlan0") or "no IP"

    display.draw_text_lines([
        f"> {phase}",
        f"CH:{ch:02}/{total:02}  RP:{rep:02}/{rep_total:02}",
        f"ET: {et_str}",
        f"IP: {ip}",
    ])


def draw_done():
    """Display concise completion summary with duration and timestamp."""
    ch = display_info.get("channel", 0)
    total = display_info.get("total", 0)
    rep = display_info.get("repeat", 0)
    rep_total = display_info.get("repeat_total", 0)
    duration = display_info.get("duration", "--:--")
    aborted = display_info.get("aborted", False)
    now = datetime.now().strftime("%d.%m.%Y %H:%M")

    if aborted:
        title = "ABORTED..."
    else:
        title = "MEASUREMENT DONE"

    display.draw_text_lines([
        title,
        f"CH:{ch:02}/{total:02}  RP:{rep:02}/{rep_total:02}",
        f"ET: {duration}",
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
        state = display_info.get("state", "idle")

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
def update_measurement_state(phase, ch, total, rep, rep_total):
    """Convenience helper called from measurement thread."""
    # Mark start time when a new measurement begins
    if phase == "MEASURING" and display_info.get("start_time") is None:
        display_info["start_time"] = time.time()
        display_info["stop_time"] = None
        display_info["duration"] = None

    display_info.update({
        "state": "run",
        "phase": phase,
        "channel": ch,
        "total": total,
        "repeat": rep,
        "repeat_total": rep_total
    })

def show_run_complete(duration, aborted: bool = False):
    """
    Display the completion summary on the OLED.
    Duration is expected in seconds (float or int).
    """
    display_info["stop_time"] = time.time()

    # Format the provided duration
    if isinstance(duration, (int, float)) and duration >= 0:
        hours = int(duration // 3600)
        minutes = int((duration % 3600) // 60)
        seconds = int(duration % 60)
        if hours > 0:
            display_info["duration"] = f"{hours:02}:{minutes:02}:{seconds:02}"
        else:
            display_info["duration"] = f"{minutes:02}:{seconds:02}"
    else:
        display_info["duration"] = "--:--"

    display_info["state"] = "done"
    display_info["aborted"] = aborted

    # Background worker to revert display after timeout
    def _revert_to_idle():
        time.sleep(10)
        display_info.update({
            "state": "idle",
            "start_time": None,
            "stop_time": None,
        })

    threading.Thread(target=_revert_to_idle, daemon=True).start()

def start_display_thread():
    t = threading.Thread(target=display_updater, daemon=True)
    t.start()
