from __future__ import annotations
from typing import Dict, Any, Tuple

def build_sse_state(progress: Dict[str, Any] | None,
                    connection: Dict[str, Any] | None,
                    live_data: Dict[str, Any] | None,
                    usb_mounted: bool | None = None,
                    buzzer_enabled: bool | None = None) -> Dict[str, Any]:
    """
    Assemble SSE state payload from component snapshots.
    
    Strategy: Always send progress (changes every 0.5-1s), only send other fields when changed.
    - Progress: Always included (phase, percent, channel, etc. - changes frequently)
    - Connection, live_data, USB, buzzer: Only included when changed (rare events)
    
    Frontend uses `?? null` or `if (field)` checks to handle missing fields.
    Payload-level deduplication prevents redundant sends.
    
    Args:
        progress: Progress dict from acquisition engine (always sent)
        connection: Connection dict or None if unchanged
        live_data: Live measurement data or None if unchanged
        usb_state: USB state tuple or None if unchanged
        buzzer_enabled: Buzzer state or None if unchanged
    
    Returns:
        State dict with progress + any changed fields
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
