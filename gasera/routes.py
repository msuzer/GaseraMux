from flask import Blueprint, jsonify, Response, stream_with_context, request
from system.preferences import prefs
from gasera.acquisition_engine import AcquisitionEngine
from gpio.pneumatic_mux import build_default_cascaded_mux
from gpio.pin_assignments import OC1_PIN, OC2_PIN, OC3_PIN, OC4_PIN
from system.log_utils import info, warn, error
from .controller import gasera
from .trigger_monitor import TriggerMonitor
import time, json
import threading
from datetime import datetime

gasera_bp = Blueprint("gasera", __name__)

# ----------------------------------------------------------------------
# Singleton setup
# ----------------------------------------------------------------------
cmux = build_default_cascaded_mux(
    mux1_home_pin=OC1_PIN,
    mux1_next_pin=OC2_PIN,
    mux2_home_pin=OC3_PIN,
    mux2_next_pin=OC4_PIN,
)
engine = AcquisitionEngine(cmux)
trigger = TriggerMonitor(engine)
trigger.start()

latest_progress = {"phase": "IDLE", "virtual_channel": 0, "repeat_index": 0}
latest_connection = {"online": False}
latest_live_data = {}

# ----------------------------------------------------------------------
# Progress subscription
# ----------------------------------------------------------------------
def on_progress_update(progress):
    """Normalize progress updates whether given as an object or dict."""
    global latest_progress
    if isinstance(progress, dict):
        latest_progress = progress
    else:
        # Convert dataclass or object to plain dict
        try:
            latest_progress = progress.__dict__.copy()
        except AttributeError:
            # Fallback: manual attribute extraction
            latest_progress = {
                "phase": getattr(progress, "phase", "IDLE"),
                "virtual_channel": getattr(progress, "virtual_channel", 0),
                "repeat_index": getattr(progress, "repeat_index", 0),
            }

engine.subscribe(on_progress_update)

def background_status_updater():
    """Periodically refresh connection and live data for SSE clients."""
    global latest_connection, latest_live_data
    while True:
        try:
            # Connection status
            latest_connection = {"online": gasera.is_connected()}

            # Live measurement data (safe & lightweight)
            result = gasera.acon_proxy()
            if isinstance(result, dict) and result.get("components"):
                latest_live_data = {
                    "timestamp": result.get("readable"),
                    "components": {
                        c["label"]: float(c["ppm"]) for c in result["components"]
                    }
                }
            else:
                latest_live_data = {}

        except Exception as e:
            error(f"[SSE] background updater error: {e}")

        time.sleep(25.0)  # adjust frequency as needed

threading.Thread(target=background_status_updater, daemon=True).start()

# ----------------------------------------------------------------------
# Connection & live data
# ----------------------------------------------------------------------
@gasera_bp.route("/api/connection_status")
def gasera_api_connection_status() -> tuple[Response, int]:
    return jsonify({"ok": True, "online": gasera.is_connected()}), 200

@gasera_bp.route("/api/data/live")
def gasera_api_data_live() -> tuple[Response, int]:
    result = gasera.acon_proxy()

    if isinstance(result, dict) and not result.get("error") and result.get("components"):
        if "string" not in result:
            lines = [f"{c['label']}: {float(c['ppm']):.4f} ppm" for c in result["components"]]
            result["string"] = f"Measurement Results ({result['readable']}):\n" + "\n".join(lines)
        return jsonify(result), 200

    msg = "No measurement data yet"
    if isinstance(result, dict) and result.get("error"):
        msg = str(result["error"])
    elif result is None:
        msg = "No response from device"
    elif not isinstance(result, dict):
        msg = "Unexpected upstream response"

    return jsonify({"message": msg}), 200

# ----------------------------------------------------------------------
# Measurement control
# ----------------------------------------------------------------------
@gasera_bp.route("/api/measurement/start", methods=["POST"])
def start_measurement() -> tuple[Response, int]:
    data = request.get_json(silent=True) or {}
    try:
        prefs.update_from_dict(data)
        started, msg = engine.start()

        return jsonify({"ok": started, "message": msg}), 200

    except Exception as e:
        error(f"[MEAS] start failed: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@gasera_bp.route("/api/measurement/abort", methods=["POST"])
def abort_measurement() -> tuple[Response, int]:
    if not engine.is_running():
        info("[MEAS] abort ignored (no active measurement)")
        return jsonify({"ok": False, "message": "No active measurement"}), 200

    engine.stop()
    return jsonify({"ok": True, "message": "Abort signal sent"}), 200

@gasera_bp.route("/api/measurement/status", methods=["GET"])
def get_status():
    return jsonify({"ok": True, "progress": engine.get_progress()}), 200

# ----------------------------------------------------------------------
# Server-Sent Events
# ----------------------------------------------------------------------
@gasera_bp.route("/api/measurement/events")
def sse_events():
    """SSE stream emitting current progress/phase."""
    def event_stream():
        last_payload = None
        last_beat = time.monotonic()

        while True:
            try:
                state = {
                    **(latest_progress.copy() if latest_progress else engine.get_progress()),
                    "connection": latest_connection,
                    "live_data": latest_live_data.copy()
                }

                # always include live_data if available
                if latest_live_data:
                    state["live_data"] = latest_live_data.copy()

                payload = json.dumps(state, sort_keys=True)

                if payload != last_payload:
                    yield f"data: {payload}\n\n"
                    yield ":\n\n"
                    last_payload = payload
                    last_beat = time.monotonic()
                    info(f"[SSE] sent update: {state}")
                elif time.monotonic() - last_beat > 10:
                    yield ": keep-alive\n\n"
                    last_beat = time.monotonic()
                    info("[SSE] sent keep-alive")

                time.sleep(0.5)

            except GeneratorExit:
                info("[SSE] client disconnected")
                break
            except Exception as e:
                error(f"[SSE] stream error: {e}")
                time.sleep(1)

    return Response(stream_with_context(event_stream()), mimetype="text/event-stream")
