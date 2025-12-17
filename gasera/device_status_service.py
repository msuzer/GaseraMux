from __future__ import annotations

import threading
import time
from typing import Dict, Any

from system.log_utils import debug, warn
from system.preferences import prefs, KEY_BUZZER_ENABLED
from gasera.controller import gasera
from .storage_utils import check_usb_change

"""
Device Status Service (refactored)
--------------------------------
Single source of truth for *low-frequency* device state snapshots used by:
- SSE payloads
- AcquisitionEngine runtime guards

Design principles:
- Gasera is polled in exactly ONE place (this module)
- Polling is rate-limited and independent of SSE clients
- All consumers read cached snapshots (no direct protocol calls)
"""

# -----------------------------------------------------------------------------
# Internal state
# -----------------------------------------------------------------------------

_latest_device_status: Dict[str, Any] = {
    "connection": {"online": False},
    "usb": {"mounted": False},
    "buzzer": {"enabled": False},
    "gasera": {},
}

_latest_usb_mounted: bool = False
_buzzer_change_pending: bool | None = None

_lock = threading.Lock()

# Polling control
_DEVICE_POLL_INTERVAL = 2.0  # seconds
_poller_thread: threading.Thread | None = None

# -----------------------------------------------------------------------------
# Public snapshot accessors
# -----------------------------------------------------------------------------

def get_device_snapshots() -> Dict[str, Any]:
    """
    Return a coherent snapshot of device status for SSE.
    This function NEVER talks to hardware or network.
    """
    with _lock:
        # Derive connection status purely from Gasera snapshot
        online = _latest_device_status.get("gasera", {}).get("online", False)
        _latest_device_status["connection"] = {"online": online}

        # USB
        _latest_device_status["usb"] = {"mounted": _latest_usb_mounted}

        # Buzzer
        enabled = bool(prefs.get(KEY_BUZZER_ENABLED, False))
        buz = {"enabled": enabled}
        if _buzzer_change_pending is not None:
            buz["_changed"] = True
        _latest_device_status["buzzer"] = buz

        return _latest_device_status.copy()


def get_latest_gasera_status() -> Dict[str, Any]:
    """Read-only accessor for cached Gasera compound status."""
    with _lock:
        return _latest_device_status.get("gasera", {}).copy()


def clear_buzzer_change() -> None:
    """Clear pending buzzer change flag after SSE send."""
    global _buzzer_change_pending
    with _lock:
        _buzzer_change_pending = None

# -----------------------------------------------------------------------------
# Internal update helpers
# -----------------------------------------------------------------------------

def _update_usb_status() -> None:
    global _latest_usb_mounted
    try:
        mounted, _ = check_usb_change()
    except Exception:
        mounted = _latest_usb_mounted

    with _lock:
        _latest_usb_mounted = mounted

def _update_gasera_status() -> None:
    try:
        dev_status = gasera.get_device_status()
    except Exception:
        with _lock:
            _latest_device_status["gasera"] = {"online": False, "error": True}
        return

    if not dev_status or dev_status.error:
        with _lock:
            _latest_device_status["gasera"] = {"online": False, "error": True}
        return

    status = {
        "online": True,
        "status": dev_status.status_str,
        "status_code": dev_status.status_code,
    }

    with _lock:
        _latest_device_status["gasera"] = status

def _update_gasera_phase() -> None:
    with _lock:
        status = _latest_device_status.get("gasera", {}).copy()

    online = status.get("online", False)
    code = status.get("status_code")

    if online and code == 5:
        try:
            meas_status = gasera.get_measurement_status()
            phase = (
                meas_status.description
                if meas_status and not meas_status.error
                else "unknown"
            )
        except Exception:
            phase = "unknown"

        with _lock:
            _latest_device_status["gasera"]["phase"] = phase

# -----------------------------------------------------------------------------
# Poller lifecycle
# -----------------------------------------------------------------------------

def start_device_status_poller() -> None:
    """
    Start background poller that periodically refreshes:
    - USB mount state (cheap)
    - Gasera compound status (TCP)
    """
    global _poller_thread
    if _poller_thread and _poller_thread.is_alive():
        return

    def _loop():
        while True:
            _update_usb_status()
            _update_gasera_status()
            time.sleep(_DEVICE_POLL_INTERVAL)
            _update_gasera_phase()
            time.sleep(_DEVICE_POLL_INTERVAL)

    _poller_thread = threading.Thread(
        target=_loop,
        name="DeviceStatusPoller",
        daemon=True,
    )
    _poller_thread.start()

# -----------------------------------------------------------------------------
# Preference callbacks
# -----------------------------------------------------------------------------

def _on_buzzer_change(key: str, value: Any) -> None:
    if key == KEY_BUZZER_ENABLED:
        global _buzzer_change_pending
        with _lock:
            _buzzer_change_pending = bool(value)
            debug(f"[DEVICE] Buzzer change detected: {value}")

prefs.add_callback(_on_buzzer_change)
