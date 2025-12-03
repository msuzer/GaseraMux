from datetime import datetime
from flask import Blueprint, jsonify, Response, stream_with_context, request
from system.preferences import prefs
from gasera.acquisition_engine import AcquisitionEngine
from gpio.pneumatic_mux import build_default_cascaded_mux
from gpio.pin_assignments import OC1_PIN, OC2_PIN, OC3_PIN, OC4_PIN, OC5_PIN
from system.log_utils import verbose, debug, info, warn, error
from gasera.controller import gasera
from gasera.trigger_monitor import TriggerMonitor
from gasera import gas_info
from gasera.sse_utils import build_sse_state
from gasera.live_status_service import (
    init as live_init,
    start_background_updater,
    stop_background_updater,
    get_snapshots,
)
import time, json
from .storage_utils import usb_mounted, check_usb_change, get_log_directory, get_free_space, get_total_space, list_log_files, safe_join_in_logdir
import os
from flask import send_file

gasera_bp = Blueprint("gasera", __name__)

# ----------------------------------------------------------------------
# Singleton setup
# ----------------------------------------------------------------------
cmux = build_default_cascaded_mux(
    mux1_home_pin=OC5_PIN,
    mux1_next_pin=OC4_PIN,
    mux2_home_pin=OC2_PIN,
    mux2_next_pin=OC1_PIN,
)
engine = AcquisitionEngine(cmux)
trigger = TriggerMonitor(engine)
trigger.start()

# Initialize live status service and start updater
live_init(engine)
start_background_updater()

# ----------------------------------------------------------------------
# Progress subscription
# ----------------------------------------------------------------------
"""
Live status management moved to gasera.live_status_service
"""

# ----------------------------------------------------------------------
# Gas metadata
# ----------------------------------------------------------------------
@gasera_bp.route("/api/gas_colors")
def gasera_api_gas_colors() -> tuple[Response, int]:
    """Return a mapping of gas labels to their display colors."""
    color_map = gas_info.build_label_to_color_map()
    return jsonify(color_map), 200

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
        debug("[MEAS] abort ignored (no active measurement)")
        return jsonify({"ok": False, "message": "No active measurement"}), 200

    warn("[MEAS] Abort requested")
    engine.stop()
    return jsonify({"ok": True, "message": "Abort signal sent"}), 200

# ----------------------------------------------------------------------
# Server-Sent Events
# ----------------------------------------------------------------------
@gasera_bp.route("/api/measurement/events")
def sse_events() -> Response:
    """SSE stream emitting current progress/phase."""
    def event_stream():
        last_payload = None
        last_beat = time.monotonic()

        while True:
            try:
                # Snapshot current status from service
                lp, lc, ld = get_snapshots()
                usb_state = check_usb_change()
                state = build_sse_state(lp, lc, ld, usb_state)

                payload = json.dumps(state, sort_keys=True)
                if payload != last_payload:
                    yield f"data: {payload}\n\n"
                    yield ":\n\n"
                    last_payload = payload
                    last_beat = time.monotonic()
                    verbose(f"[SSE] sent update: {state}")
                elif time.monotonic() - last_beat > 10:
                    yield ": keep-alive\n\n"
                    last_beat = time.monotonic()
                    verbose("[SSE] sent keep-alive")

                time.sleep(0.5)

            except GeneratorExit:
                debug("[SSE] client disconnected")
                break
            except Exception as e:
                warn(f"[SSE] stream error: {e}")
                time.sleep(1)

    return Response(stream_with_context(event_stream()), mimetype="text/event-stream")

# ----------------------------------------------------------------------
# Static file serving for gasera frontend
# ----------------------------------------------------------------------

@gasera_bp.route("/api/logs")
def list_logs():
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 50))

    result = list_log_files(page, page_size)
    result["ok"] = True
    return jsonify(result)

@gasera_bp.route("/api/logs/<path:filename>", methods=["GET"])
def download_log(filename):
    try:
        path = safe_join_in_logdir(filename)
        return send_file(path, as_attachment=True)
    except FileNotFoundError:
        return jsonify({"ok": False, "error": "File not found"}), 404
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@gasera_bp.route("/api/logs/storage", methods=["GET"])
def log_storage_info():
    usb_root = "/media/usb0"
    usb_path = "/media/usb0/logs"
    internal_path = "/data/logs"

    mounted = usb_mounted()

    os.makedirs(internal_path, exist_ok=True)
    if mounted:
        os.makedirs(usb_path, exist_ok=True)

    info = {
        "ok": True,
        "active": "usb0" if mounted else "internal",
        "usb": {
            "mounted": mounted,
            "free": get_free_space(usb_path) if mounted else None,
            "total": get_total_space(usb_root) if mounted else None
        },
        "internal": {
            "free": get_free_space(internal_path),
            "total": get_total_space("/")
        }
    }
    
    return jsonify(info), 200

@gasera_bp.route("/api/logs/delete/<path:filename>", methods=["DELETE"])
def delete_log(filename):
    try:
        path = safe_join_in_logdir(filename)
        os.remove(path)
        return jsonify({"ok": True}), 200
    except FileNotFoundError:
        return jsonify({"ok": False, "error": "File not found"}), 404
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@gasera_bp.route("/api/logs/delete_all", methods=["DELETE"])
def delete_all_logs():
    log_dir = get_log_directory()
    try:
        files = [f for f in os.listdir(log_dir) if f.lower().endswith(".csv")]
        for f in files:
            os.remove(os.path.join(log_dir, f))
        return jsonify({"ok": True, "deleted_files": len(files)}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500