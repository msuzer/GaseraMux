from __future__ import annotations
from typing import Dict, Any, Tuple


class SseDeltaTracker:
    """
    Tracks last-sent device snapshots to include only changed fields in SSE payloads.

    Usage:
        tracker = SseDeltaTracker()
        state = tracker.build(lp, ld, lc, lu, lb)
    """

    def __init__(self) -> None:
        self._last_live_data: Dict[str, Any] | None = None
        self._last_connection: Dict[str, Any] | None = None
        self._last_usb_mounted: bool | None = None

    def build(
        self,
        progress: Dict[str, Any] | None,
        live_data: Dict[str, Any] | None,
        connection: Dict[str, Any] | None,
        usb_mounted: bool | None,
        buzzer_enabled: bool | None,
    ) -> Dict[str, Any]:
        """Return SSE state including only changed fields along with current progress."""
        # Determine diffs
        connection_changed = connection is not None and connection != self._last_connection
        usb_changed = usb_mounted is not None and usb_mounted != self._last_usb_mounted
        live_data_changed = bool(live_data) and live_data != self._last_live_data

        if connection_changed:
            self._last_connection = connection
        if usb_changed:
            self._last_usb_mounted = usb_mounted
        if live_data_changed:
            self._last_live_data = live_data

        # Only include changed snapshots; progress is always included
        return SseDeltaTracker.build_state(
            progress,
            connection if connection_changed else None,
            live_data if live_data_changed else None,
            usb_mounted if usb_changed else None,
            buzzer_enabled,
        )

    @staticmethod
    def build_state(
        progress: Dict[str, Any] | None,
        connection: Dict[str, Any] | None,
        live_data: Dict[str, Any] | None,
        usb_mounted: bool | None = None,
        buzzer_enabled: bool | None = None,
    ) -> Dict[str, Any]:
        """
        Assemble SSE state payload from component snapshots.

        Strategy: Always send progress (changes every 0.5-1s), only send other fields when changed.
        - Progress: Always included (phase, percent, channel, etc. - changes frequently)
        - Connection, live_data, USB, buzzer: Only included when changed (rare events)

        Frontend uses `?? null` or `if (field)` checks to handle missing fields.
        Payload-level deduplication prevents redundant sends.
        """
        # Always include progress (changes frequently, frontend needs it)
        state = progress.copy() if progress else {}

        # Only include connection when present (changed)
        if connection is not None:
            state["connection"] = connection

        # Only include live_data when present (new measurement)
        if live_data is not None and live_data:  # Non-empty dict
            state["live_data"] = live_data

        # Only include USB state when present (mount/unmount event)
        if usb_mounted is not None:
            state["usb_mounted"] = usb_mounted

        # Only include buzzer when changed
        if buzzer_enabled is not None:
            state["buzzer_enabled"] = buzzer_enabled

        return state
