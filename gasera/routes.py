from flask import Blueprint, jsonify, Response, stream_with_context, request
from system.preferences import prefs
from gasera.acquisition_engine import AcquisitionEngine
from gpio.pneumatic_mux import build_default_cascaded_mux
from gpio.pin_assignments import OC1_PIN, OC2_PIN, OC3_PIN, OC4_PIN
from system.log_utils import info, warn, error
from .controller import gasera
from .trigger_monitor import TriggerMonitor
import time, json

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

latest_progress = {}

def on_progress_update(progress):
    global latest_progress
    latest_progress = progress.__dict__

engine.subscribe(on_progress_update)

# ----------------------------------------------------------------------
# Connection & live data
# ----------------------------------------------------------------------
@gasera_bp.route("/api/connection_status")
def gasera_api_connection_status() -> tuple[Response, int]:
    return jsonify({"ok": True, "online": gasera.check_device_connection()}), 200


@gasera_bp.route("/api/data/live")
def gasera_api_data_live() -> tuple[Response, int]:
    result = gasera.acon_proxy()

    # Success path: dict, no error, has components
    if isinstance(result, dict) and not result.get("error") and result.get("components"):
        if "string" not in result:
            lines = [f"{c['label']}: {float(c['ppm']):.4f} ppm" for c in result["components"]]
            result["string"] = f"Measurement Results ({result['readable']}):\n" + "\n".join(lines)
        return jsonify(result), 200

    # Any non-data case → return a single-line message (200)
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
        # Save all valid preferences directly
        prefs.update_from_dict(data)
        started = engine.start()
        msg = "Measurement started" if started else "Measurement already running"
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
    warn("Measurement abort requested")
    return jsonify({"ok": True, "message": "Abort signal sent"}), 200


@gasera_bp.route("/api/measurement/status", methods=["GET"])
def get_status():
    return jsonify({"ok": True, "progress": engine.get_progress()}), 200


@gasera_bp.route("/api/measurement/events")
def sse_events():
    """Server-Sent Events stream of phase/channel updates."""
    def event_stream():
        last_phase = None
        try:
            while True:
                if not engine.is_running() and not latest_progress:
                    time.sleep(0.5)
                    continue

                state = latest_progress.copy() if latest_progress else engine.get_progress()
                phase = state.get("phase")
                if phase != last_phase:
                    payload = json.dumps(state)
                    yield f"data: {payload}\n\n"
                    last_phase = phase
                time.sleep(0.5)
        except GeneratorExit:
            info("[SSE] client disconnected")

    return Response(stream_with_context(event_stream()), mimetype="text/event-stream")
