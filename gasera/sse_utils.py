from __future__ import annotations
from typing import Dict, Any, Tuple

def build_sse_state(progress: Dict[str, Any] | None,
                    connection: Dict[str, Any] | None,
                    live_data: Dict[str, Any] | None,
                    usb_state: Tuple[bool, str | None] | None) -> Dict[str, Any]:
    """
    Normalize and assemble SSE state payload.
    Ensures live_data structure is consistent and attaches USB info.
    Note: progress, connection, and live_data are already copies from get_snapshots()
    """
    # Reuse the progress dict directly (already a copy from get_snapshots)
    state = progress or {}
    state["connection"] = connection or {}
    state["live_data"] = live_data or {"timestamp": None, "components": []}

    if usb_state:
        mounted, event = usb_state
        state["usb_mounted"] = mounted
        if event:
            state["usb_event"] = event

    return state
