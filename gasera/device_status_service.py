from __future__ import annotations
import threading
from typing import Dict, Any, Tuple

from system.log_utils import info, debug
from gasera.controller import gasera
from system.preferences import prefs, KEY_BUZZER_ENABLED
from .storage_utils import check_usb_change

# Device state snapshots (low-frequency changes)
latest_connection: Dict[str, Any] = {"online": False}
latest_usb_mounted: bool = False
_buzzer_change_pending: bool | None = None

_lock = threading.Lock()


def get_device_snapshots() -> Tuple[Dict[str, Any], bool | None, bool | None]:
    """
    Get all device status snapshots in a single locked operation.
    Returns: (connection, usb_state, buzzer_change)
    Note: Buzzer change is NOT consumed here; caller must call clear_buzzer_change() after successful send.
    """
    with _lock:
        conn = latest_connection.copy()
        usb = latest_usb_mounted
        buzzer = _buzzer_change_pending
        return conn, usb, buzzer

def clear_buzzer_change() -> None:
    """Clear the buzzer change flag after it has been successfully sent."""
    global _buzzer_change_pending
    with _lock:
        _buzzer_change_pending = None

def update_connection_state() -> None:
    """Update connection state (called by live_status_service background thread)."""
    global latest_connection
    conn = {"online": gasera.is_connected()}
    with _lock:
        latest_connection = conn

def set_usb_state(mounted: bool, event: str | None) -> None:
    """Update USB state (called by storage_utils event monitor)."""
    global latest_usb_mounted
    with _lock:
        latest_usb_mounted = mounted

def update_all_device_status() -> None:
    """
    Update all device status: connection and USB.
    Called from SSE stream before fetching snapshots.
    """
    update_connection_state()
    usb_mounted, usb_event = check_usb_change()
    set_usb_state(usb_mounted, usb_event)

def _on_buzzer_change(key: str, value: Any) -> None:
    """Callback for preference changes to track buzzer state updates."""
    if key == KEY_BUZZER_ENABLED:
        global _buzzer_change_pending
        with _lock:
            _buzzer_change_pending = bool(value)
            debug(f"[DEVICE] Buzzer change detected: {value}")

# Register callback for buzzer preference changes
prefs.add_callback(_on_buzzer_change)
