from __future__ import annotations
import threading
import time
from datetime import datetime
from typing import Dict, Any, Tuple

from system.log_utils import debug, warn, error
from gasera.controller import gasera
from gasera.acquisition_engine import AcquisitionEngine

# High-frequency data snapshots (progress + live measurements)
latest_progress: Dict[str, Any] = {"phase": "IDLE", "current_channel": 0, "repeat_index": 0}
latest_live_data: Dict[str, Any] = {}

_lock = threading.Lock()  # Protect access to latest_* globals
SSE_UPDATE_INTERVAL = 25.0
_updater_stop_event = threading.Event()

_engine: AcquisitionEngine | None = None


def init(engine: AcquisitionEngine) -> None:
    global _engine
    _engine = engine
    engine.subscribe(_on_progress_update)

def _on_progress_update(progress) -> None:
    global latest_progress
    try:
        if isinstance(progress, dict):
            with _lock:
                latest_progress.update(progress)
        else:
            # Convert Progress object to dict with all fields
            new_progress = {
                "phase": progress.phase,
                "current_channel": progress.current_channel,
                "next_channel": progress.next_channel,
                "percent": progress.percent,
                "overall_percent": progress.overall_percent,
                "repeat_index": progress.repeat_index,
                "repeat_total": progress.repeat_total,
                "enabled_count": progress.enabled_count,
                "step_index": progress.step_index,
                "total_steps": progress.total_steps,
                "elapsed_seconds": progress.elapsed_seconds,
                "tt_seconds": progress.tt_seconds,
            }
            with _lock:
                latest_progress = new_progress
    except Exception as e:
        warn(f"[live] progress update error: {e}")


def start_background_updater() -> None:
    t = threading.Thread(target=_background_status_updater, daemon=True, name="sse-updater")
    t.start()


def stop_background_updater() -> None:
    _updater_stop_event.set()


def _background_status_updater() -> None:
    """Background thread for high-frequency data: progress updates and live gas measurements."""
    global latest_live_data
    while not _updater_stop_event.is_set():
        try:
            if _engine and _engine.is_running():
                result = gasera.acon_proxy()
                if isinstance(result, dict) and result.get("components"):
                    progress = _engine.progress

                    # Timestamp selection
                    if result.get("timestamp") is not None:
                        ts_epoch = result["timestamp"]
                        try:
                            ts = datetime.fromtimestamp(ts_epoch).strftime("%Y-%m-%d %H:%M:%S")
                        except Exception:
                            ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                    elif result.get("readable"):
                        ts = result["readable"]
                    else:
                        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                        warn(f"[live] No timestamp from device, using local timestamp: {ts}")

                    live_data = {
                        "timestamp": ts,
                        "phase": progress.phase,
                        "channel": progress.current_channel + 1,
                        "repeat": progress.repeat_index,
                        "components": [
                            {
                                "label": c["label"],
                                "ppm": float(c["ppm"]),
                                "color": c["color"],
                                "cas": c["cas"],
                            }
                            for c in result["components"]
                        ],
                    }

                    try:
                        is_new = _engine.on_live_data(live_data)
                        with _lock:
                            latest_live_data = live_data if is_new else {}
                    except Exception as e:
                        warn(f"[live] on_live_data error: {e}")
                else:
                    with _lock:
                        latest_live_data = {}
        except Exception as e:
            error(f"[live] background updater error: {e}")
        time.sleep(SSE_UPDATE_INTERVAL)

def get_live_snapshots() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Get high-frequency data snapshots: progress and live measurements."""
    with _lock:
        return latest_progress.copy(), latest_live_data.copy()
