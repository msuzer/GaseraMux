# SSE Payload: Measurement Progress

This document describes the JSON payload streamed by `/api/measurement/events`.

All fields are computed on the backend. The frontend renders values directly without any additional calculations.

## Progress Fields

- phase: Current phase. One of: IDLE, HOMING, PAUSED, MEASURING, SWITCHING, ABORTED
- current_channel: 0-based index of the currently selected physical channel
- next_channel: 0-based index of the next physical channel (UI adds +1 for display)
- percent: Percent complete within the current repeat (integer 0-100)
- overall_percent: Percent complete across the entire run (integer 0-100)
- repeat_index: 1-based index of the current repeat (1..repeat_total)
- repeat_total: Total number of repeats configured
- enabled_count: Number of enabled channels in the mask
- step_index: Completed-only step counter across the entire run
  - Increments only after a channel measurement finishes (before/while SWITCHING)
  - Does not include the current in-progress channel during PAUSED/MEASURING/HOMING
- total_steps: repeat_total * enabled_count
- elapsed_seconds: Seconds since run start (updates in all active phases)
- tt_seconds: Estimated total time for the run (ET + TT formatting happens on the client)

## Conventions

- Channels are 0-based in SSE. UI displays 1-based by adding +1.
- step_index is completed-only; clients should not recalculate it.
- elapsed_seconds and tt_seconds are backend-provided; clients should not derive timers locally.

## Update Cadence

The backend emits periodic progress updates during all active phases:
- HOMING: updates during settle
- PAUSED: updates during pause
- MEASURING: updates during measurement
- SWITCHING: updates during settle (and last-channel 1s signal)

This keeps timers and UI in sync across phase changes without client-side timers.
