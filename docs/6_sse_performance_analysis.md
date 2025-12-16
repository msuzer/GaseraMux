# SSE Performance Analysis

## Current Configuration

### Emission Rates
- **Progress updates** (during active measurement): Every 0.5-1.0s
  - HOMING: 0.5s intervals during 5s settle
  - PAUSED: 0.5s intervals during pause_seconds
  - MEASURING: 0.5-1.0s intervals during measure_seconds
  - SWITCHING: 0.5s intervals during 5s settle
- **Device polling** (live_data): Every 25s
- **SSE route polling**: Every 0.5s
- **Keep-alive**: Every 10s if no data changes

### Payload Size Estimation

#### Minimal Progress Payload (IDLE, no measurement)
```json
{
  "phase": "IDLE",
  "current_channel": 0,
  "next_channel": null,
  "percent": 0,
  "overall_percent": 0,
  "repeat_index": 0,
  "repeat_total": 0,
  "enabled_count": 0,
  "step_index": 0,
  "total_steps": 0,
  "elapsed_seconds": 0.0,
  "tt_seconds": null,
  "connection": {"online": true},
  "live_data": {"timestamp": null, "components": []},
  "usb_mounted": true
}
```
**Size: ~220 bytes**

#### Typical Active Measurement Payload
```json
{
  "phase": "MEASURING",
  "current_channel": 5,
  "next_channel": 6,
  "percent": 35,
  "overall_percent": 18,
  "repeat_index": 1,
  "repeat_total": 3,
  "enabled_count": 8,
  "step_index": 3,
  "total_steps": 24,
  "elapsed_seconds": 125.3,
  "tt_seconds": 687.5,
  "connection": {"online": true},
  "live_data": {
    "timestamp": "2025-12-03 14:32:15",
    "phase": "MEASURING",
    "channel": 6,
    "repeat": 1,
    "components": [
      {"label": "CH4", "ppm": 2.456, "color": "#FF5733", "cas": "74-82-8"},
      {"label": "CO2", "ppm": 450.123, "color": "#33C1FF", "cas": "124-38-9"},
      {"label": "H2O", "ppm": 8234.5, "color": "#8E44AD", "cas": "7732-18-5"}
    ]
  },
  "usb_mounted": true
}
```
**Size: ~580 bytes** (with 3 gas components)

#### Maximum Payload (7 components)
With max 7 gas components: **~850 bytes**

## Bandwidth Analysis

### Active Measurement (worst case)
- Update frequency: 2 updates/second (0.5s interval)
- Payload size: 850 bytes (max)
- **Bandwidth: 1.7 KB/s = 13.6 Kbps**

### Idle State
- Keep-alive frequency: 0.1 updates/second (10s interval)
- Payload size: 220 bytes
- **Bandwidth: 22 bytes/s = 176 bps**

## Current Assessment

### ✅ Good Aspects
1. **Small payload**: 220-850 bytes is very reasonable
2. **Efficient change detection**: Only sends when payload differs
3. **Smart keep-alive**: 10s interval prevents connection timeout without spam
4. **Conditional updates**: Device polling (25s) is separate from UI updates (0.5s)
5. **Lock-protected snapshots**: Thread-safe with minimal contention

### ⚠️ Potential Issues

#### 1. High-Frequency Progress Updates
**Current**: 0.5-1.0s updates during all active phases
**Impact**: 
- 2 updates/sec × 850 bytes = 1.7 KB/s per client
- For 5 concurrent clients: 8.5 KB/s
- For embedded device (Orange Pi Zero 3), this is fine but could accumulate

**Recommendation**: 
- Current rate is acceptable for measurement visibility
- Consider adding `SSE_UPDATE_INTERVAL` constant (default 0.5s) for easy tuning
- Could reduce to 1.0s during PAUSED/SWITCHING if UI responsiveness allows

#### 2. Live Data Duplication
**Current**: `live_data` included in every SSE update
**Impact**: 
- Adds ~360 bytes even when it hasn't changed (25s refresh)
- During the 25s between device polls, same `live_data` sent 50 times

**Recommendation**:
- Split into two SSE streams: `/api/measurement/progress` and `/api/measurement/live-data`
- OR: Only include `live_data` when it changes (compare timestamp)
- OR: Add `live_data_updated` flag and let frontend cache it

#### 3. No Payload Compression
**Current**: Plain JSON, no gzip
**Impact**: 
- 850 bytes could compress to ~300-400 bytes
- For local network, compression overhead may exceed benefit

**Recommendation**:
- Keep uncompressed for local deployment (simpler, lower CPU)
- Add compression only if deploying over WAN

#### 4. USB State in Every Update
**Current**: `usb_mounted` and `usb_event` in every payload
**Impact**: 
- +20 bytes per update
- Changes infrequently (only on USB plug/unplug)

**Recommendation**:
- Move to separate `/api/system/usb` endpoint polled every 5-10s
- OR: Only include when USB state changes

## Recommendations Summary

### Priority 1: Split Live Data (Optional Optimization)
```python
# Separate live_data updates to avoid duplication
@gasera_bp.route("/api/measurement/live-data/events")
def live_data_events():
    # Only emit when components change (every 25s from device)
    ...
```

### Priority 2: Add Tunable Constants
```python
# In acquisition_engine.py
SSE_NOTIFY_INTERVAL_FAST = 0.5  # during MEASURING
SSE_NOTIFY_INTERVAL_SLOW = 1.0  # during PAUSED/HOMING/SWITCHING
```

### Priority 3: Conditional live_data Inclusion
```python
# In sse_utils.py - only include live_data if timestamp changed
def build_sse_state(...):
    state = progress or {}
    state["connection"] = connection or {}
    
    # Only include live_data if it has a timestamp (i.e., real data)
    if live_data and live_data.get("timestamp"):
        state["live_data"] = live_data
    
    ...
```

## Conclusion

**Current design is well-optimized** for a local embedded deployment:
- Payload sizes are small (220-850 bytes)
- Bandwidth usage is low (1.7 KB/s worst case)
- Change detection prevents unnecessary updates
- Thread-safe implementation

**No critical issues** - system can handle current load easily.

**Optional optimizations** listed above can reduce bandwidth by 40-60% if needed for:
- Multiple concurrent clients (>10)
- WAN deployment
- Very constrained networks

For current use case (single/few clients on local network), **no immediate action required**.
