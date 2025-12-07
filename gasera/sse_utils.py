from __future__ import annotations
from typing import Dict, Any

class SseDeltaTracker:
    """
    Tracks last-sent device snapshots to include only changed fields in SSE payloads.

    Usage:
        tracker = SseDeltaTracker()
        state = tracker.build(lp, ld, lc, lu, lb)
    """

    def __init__(self) -> None:
        self._last_live_data: Dict[str, Any] | None = None
        self._last_device_status: Dict[str, Any] | None = None

    def build(
        self,
        progress: Dict[str, Any] | None,
        live_data: Dict[str, Any] | None,
        device_status: Dict[str, Any] | None,
    ) -> Dict[str, Any]:
        """Return SSE state including only changed fields along with current progress."""
        # Determine diffs
        device_changed = device_status is not None and device_status != self._last_device_status
        live_data_changed = bool(live_data) and live_data != self._last_live_data

        if device_changed:
            self._last_device_status = device_status
        if live_data_changed:
            self._last_live_data = live_data

        # Only include changed snapshots; progress is always included
        return SseDeltaTracker.build_state(
            progress,
            device_status if device_changed else None,
            live_data if live_data_changed else None,
        )

    @staticmethod
    def build_state(
        progress: Dict[str, Any] | None,
        device_status: Dict[str, Any] | None,
        live_data: Dict[str, Any] | None,
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
        # Snapshot is already copied by get_live_snapshots(); avoid redundant copy here.
        state = progress or {}

        # Only include compound device_status when present (changed)
        if device_status is not None:
            state["device_status"] = device_status

        # Only include live_data when present (new measurement)
        if live_data is not None and live_data:  # Non-empty dict
            state["live_data"] = live_data

        # Marker is embedded by device_status_service; no need to set here.

        return state
