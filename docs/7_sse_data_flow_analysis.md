# SSE Data Flow Analysis

## Overview

This document analyzes the Server-Sent Events (SSE) architecture in GaseraMux, detailing what data is transmitted, when it's sent, and at what frequencies.

## SSE Message Payload Structure

Every SSE message contains the following JSON structure:

```json
{
  // Progress data (from acquisition_engine)
  "phase": "IDLE|HOMING|MEASURING|PAUSED|SWITCHING|ABORTED",
  "current_channel": 0-30,
  "next_channel": null | 0-30,
  "percent": 0-100,              // per-repeat progress
  "overall_percent": 0-100,      // overall progress across all repeats
  "repeat_index": 0-n,           // current repeat (0-based)
  "repeat_total": n,             // total repeats configured
  "enabled_count": n,            // number of enabled channels
  "step_index": n,               // completed measurements (0-based)
  "total_steps": n,              // total measurements across all repeats
  "elapsed_seconds": 123.45,     // time since measurement start
  "tt_seconds": 456.78,          // total time estimate
  
  // Connection status (from tcp_client)
  "connection": {
    "online": true/false         // Gasera TCP connection state
  },
  
  // Live measurement data (from Gasera ACON, only during active measurement)
  "live_data": {
    "timestamp": "2025-12-04 12:34:56",
    "phase": "MEASURING",
    "channel": 1-31,
    "repeat": 0-n,
    "components": [
      {
        "label": "CO2",
        "ppm": 123.45,
        "color": "#ff0000",
        "cas": "124-38-9"
      }
      // ... more gas components
    ]
  },
  
  // USB status (when change detected)
  "usb_mounted": true/false,
  "usb_event": "mounted|unmounted|null"
}
```

## SSE Broadcasting Mechanism

### 1. Change-Based Broadcasting
**Location:** `gasera/routes.py:~100`

```python
if payload != last_payload:
    yield f"data: {payload}\n\n"
```

- SSE sends **only when state changes**
- Prevents unnecessary network traffic
- Compares JSON payload strings to detect changes

### 2. Polling Rate: 500ms
**Location:** `gasera/routes.py:~118`

```python
time.sleep(0.5)
```

- Backend checks for state changes **2x per second**
- Latency: <1 second for any state change to reach clients

### 3. Keep-Alive: Every 10 seconds
**Location:** `gasera/routes.py:~108`

```python
elif time.monotonic() - last_beat > 10:
    yield ": keep-alive\n\n"
```

- If no state changes for 10 seconds, sends keep-alive comment
- Prevents HTTP connection timeout
- Does not trigger `onmessage` event in clients

## Data Source Components

### Progress Updates (acquisition_engine.py)

The acquisition engine pushes progress updates via callback subscription:

```python
engine.subscribe(_on_progress_update)  # live_status_service.py
```

#### Phase Transition Events

| Event | Phase | Frequency | Notify Called? | Location |
|-------|-------|-----------|----------------|----------|
| Start measurement | `HOMING` | Once per run | Yes | `_set_phase()` line 388 |
| Home multiplexer | `HOMING` | Once per run | Yes | `_home_mux()` |
| Pause before measure | `PAUSED` | Per channel | Yes | `_measure_channel()` via `_blocking_wait()` |
| Measuring gas | `MEASURING` | Per channel | Yes | `_measure_channel()` via `_blocking_wait()` |
| Switching channel | `SWITCHING` | Per channel | Yes | `_switch_to_next_channel()` via `_blocking_wait()` |
| Abort | `ABORTED` | Once | Yes | `_finalize_run()` |
| Complete | `IDLE` | Once | Yes | `_finalize_run()` |

#### Progress Update Frequency During Active Phases

**Location:** `acquisition_engine.py:_blocking_wait()` line 342

```python
def _blocking_wait(self, duration: float, notify: bool = True) -> bool:
    interval = 0.5 if duration < 10 else 1.0
    while time.monotonic() < end_time:
        if notify:
            self._update_common_progress()
            self._notify()  # → triggers SSE broadcast
        time.sleep(interval)
```

- **Short waits (<10s):** Updates every **0.5 seconds**
  - Applies to: SWITCHING phase (5s settle time)
- **Long waits (≥10s):** Updates every **1.0 second**
  - Applies to: MEASURING, PAUSED phases

### Connection Status (tcp_client.py)

**Updated by:** Background connection monitor thread
**Frequency:** Continuous monitoring with debounced state changes
**Location:** `live_status_service.py:_background_status_updater()`

```python
conn = {"online": gasera.is_connected()}
with _lock:
    latest_connection = conn
```

- Checks connection status during each background update cycle
- SSE broadcasts only when connection state changes (online ↔ offline)

### Live Gas Data (live_status_service.py)

**Background thread polling Gasera ACON for real-time measurements:**

```python
SSE_UPDATE_INTERVAL = 25.0  # line 15
```

**Frequency:** Every **25 seconds** during active measurement

**Process:**
1. Background thread calls `gasera.acon_proxy()` to fetch current gas concentrations
2. Parses component data (gas labels, PPM values, colors, CAS numbers)
3. Adds timestamp and context (phase, channel, repeat)
4. Updates `latest_live_data` in locked scope
5. SSE broadcasts on next 500ms poll (if data changed)

**Active only when:**
- Engine is running (`_engine.is_running()`)
- Gasera returns valid ACON data with components

### USB State (storage_utils.py)

**Event-driven monitoring:** Filesystem watcher detects mount/unmount events

**Location:** `routes.py:check_usb_change()`

- Tracks USB drive mount/unmount events
- Returns `(mounted: bool, event: str | None)` tuple
- SSE broadcasts immediately on state change

## Summary Table: Update Frequencies

| Data Type | Update Trigger | Base Frequency | SSE Broadcast Condition |
|-----------|---------------|----------------|------------------------|
| **Phase changes** | Engine state transitions | Per phase change | Immediately on next 500ms poll |
| **Progress (active)** | `_blocking_wait()` during phases | 0.5s (short) / 1.0s (long) | Change-based |
| **Connection status** | TCP client monitoring | Continuous | On state change only |
| **Live gas data** | Gasera ACON polling | Every **25 seconds** | On data change only |
| **USB events** | Filesystem monitoring | Event-driven | On mount/unmount only |
| **Keep-alive** | No changes for 10s | Every 10s (idle) | Always (when idle) |

## Client-Side Reception

**Location:** `static/js/core_index.js`

```javascript
window.gaseraSSE = new EventSource(API_PATHS?.measurement?.events);
window.gaseraSSE.onmessage = e => {
    const data = JSON.parse(e.data || "{}");
    window.GaseraHub.emit(data);  // Broadcast to all subscribers
};
```

- All clients receive identical SSE streams
- Client-side `GaseraHub` pub/sub distributes updates to modules
- Each module subscribes to relevant state changes

## Multi-Client Scalability

### Current Architecture Load Analysis

With **3 concurrent clients** (maximum expected):

- **Backend SSE checks:** 2/sec (500ms poll)
- **State change broadcasts:** Variable, depends on phase activity
  - Idle: ~1 keep-alive per 10 seconds
  - Active measurement: 0.5-2 updates/sec (during blocking waits)
- **Live data polls:** 1 per 25 seconds (only during measurement)

**Total network writes per state change:**
- 1 JSON serialization
- 3 network writes (one per client)
- Negligible CPU/memory overhead for 3 clients

### Bottleneck Analysis

**Not a bottleneck because:**
1. ✅ Change-based broadcasting prevents spam
2. ✅ 500ms polling provides <1s latency
3. ✅ 3 clients × 2 checks/sec = 6 lookups/sec (trivial load)
4. ✅ 25-second live data interval balances freshness vs. device I/O
5. ✅ Synchronous Flask SSE adequate for <10 clients

**Would become bottleneck at:** >50 concurrent clients (would need async SSE or Redis pub/sub)

## Key Design Principles

1. **Efficiency:** Change-based broadcasting minimizes network traffic
2. **Responsiveness:** 500ms polling ensures sub-second UI updates
3. **Consistency:** All clients receive identical state updates simultaneously
4. **Reliability:** Keep-alive prevents connection timeouts during idle periods
5. **Scalability:** Linear O(n) broadcast acceptable for lab instrument use case

## Implementation Files

| File | Purpose |
|------|---------|
| `gasera/routes.py` | SSE endpoint, event streaming loop |
| `gasera/live_status_service.py` | State aggregation, background polling |
| `gasera/acquisition_engine.py` | Progress updates, phase management |
| `gasera/sse_utils.py` | Payload builder (normalizes structure) |
| `gasera/tcp_client.py` | Connection monitoring |
| `gasera/storage_utils.py` | USB event detection |
| `static/js/core_index.js` | Client-side SSE reception, GaseraHub pub/sub |

## Related Documentation

- [SSE Payload Structure](5_sse_payload.md) - Detailed payload field descriptions
- [SSE Performance Analysis](6_sse_performance_analysis.md) - Performance measurements
- [Home Tab Architecture](../static/js/HOME_TAB_ARCHITECTURE.md) - Client-side handling

---

**Document Version:** 1.0  
**Last Updated:** December 4, 2025  
**Analyzed by:** GitHub Copilot (Claude Sonnet 4.5)
