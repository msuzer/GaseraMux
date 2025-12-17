from __future__ import annotations
import threading
import time
from typing import Dict, Any, Tuple

from system.log_utils import info, warn, debug
from gasera.controller import gasera
from system.preferences import prefs, KEY_BUZZER_ENABLED
from .storage_utils import check_usb_change

# Device state snapshots (low-frequency changes)
latest_connection: Dict[str, Any] = {"online": False}
latest_usb_mounted: bool = False
_buzzer_change_pending: bool | None = None

# Compound device status snapshot (for SSE payloads)
_latest_device_status: Dict[str, Any] = {
    "connection": {"online": False},
    "usb": {"mounted": False},
    "buzzer": {"enabled": False},
    "gasera": {}          # 👈 NEW
}

_lock = threading.Lock()


def get_device_snapshots() -> Dict[str, Any]:
    """
    Get compound device status snapshot.
    If there is a pending buzzer change, include a per-payload marker under buzzer as `_changed: true`.
    Caller should clear via `clear_buzzer_change()` after successfully sending a payload that includes this marker.
    """
    with _lock:
        _latest_device_status["connection"] = latest_connection.copy()
        _latest_device_status["usb"] = {"mounted": latest_usb_mounted}
        buz_enabled = bool(prefs.get(KEY_BUZZER_ENABLED, False))
        buz = {"enabled": buz_enabled}
        if _buzzer_change_pending is not None:
            buz["_changed"] = True
        _latest_device_status["buzzer"] = buz

        return _latest_device_status.copy()

def get_latest_gasera_status() -> Dict[str, Any]:
    """
    Read-only accessor for the most recent Gasera compound status.
    Safe for use by internal engine logic.
    """
    with _lock:
        return _latest_device_status.get("gasera", {}).copy()

def clear_buzzer_change() -> None:
    """Clear the buzzer change flag after it has been successfully sent."""
    global _buzzer_change_pending
    with _lock:
        _buzzer_change_pending = None

def _update_connection_and_usb(conn_online: bool, usb_mounted: bool) -> None:
    """Internal: atomically update connection and USB status under a single lock."""
    global latest_connection, latest_usb_mounted
    with _lock:
        latest_connection = {"online": conn_online}
        latest_usb_mounted = usb_mounted
        _latest_device_status["connection"] = latest_connection.copy()
        _latest_device_status["usb"] = {"mounted": latest_usb_mounted}

def update_gasera_status() -> None:
    try:
        gasera_status = gasera.get_compound_status()
    except Exception:
        gasera_status = {"error": True}

    with _lock:
        _latest_device_status["gasera"] = gasera_status

def update_all_device_status() -> None:
    """
    Update connection and USB in one cohesive step for consistent snapshots.
    Called from SSE stream before fetching snapshots.
    """
    try:
        conn_online = gasera.is_connected()
    except Exception:
        conn_online = False
    try:
        usb_mounted, _ = check_usb_change()
    except Exception:
        usb_mounted = latest_usb_mounted

    _update_connection_and_usb(conn_online, usb_mounted)

def _on_buzzer_change(key: str, value: Any) -> None:
    """Callback for preference changes to track buzzer state updates."""
    if key == KEY_BUZZER_ENABLED:
        global _buzzer_change_pending
        with _lock:
            _buzzer_change_pending = bool(value)
            _latest_device_status["buzzer"] = {"enabled": bool(value)}
            debug(f"[DEVICE] Buzzer change detected: {value}")

_GASERA_POLL_INTERVAL = 1.0  # seconds (safe default)
_gasera_poll_thread = None

def start_gasera_status_poller():
    global _gasera_poll_thread
    if _gasera_poll_thread and _gasera_poll_thread.is_alive():
        return
    
    def _loop():
        update_all_device_status()
        time.sleep(_GASERA_POLL_INTERVAL)
        update_gasera_status()
        time.sleep(_GASERA_POLL_INTERVAL)

    _gasera_poll_thread = threading.Thread(
        target=_loop,
        name="GaseraStatusPoller",
        daemon=True,
    )
    _gasera_poll_thread.start()

# Register callback for buzzer preference changes
prefs.add_callback(_on_buzzer_change)
