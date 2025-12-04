from flask import Blueprint, jsonify, request, Response
from system.preferences import prefs
from system.log_utils import debug, info, warn, error
from buzzer.buzzer_facade import buzzer

from system.preferences import (
    KEY_INCLUDE_CHANNELS,
    KEY_MEASUREMENT_DURATION,
    KEY_PAUSE_SECONDS,
    KEY_REPEAT_COUNT,
    KEY_BUZZER_ENABLED,
    KEY_ONLINE_MODE_ENABLED,
    KEY_TRACK_VISIBILITY)

system_bp = Blueprint("system", __name__)

# Unified default values
DEFAULTS = {
    KEY_MEASUREMENT_DURATION    : 300,
    KEY_PAUSE_SECONDS           : 300,
    KEY_REPEAT_COUNT            : 1,
    KEY_BUZZER_ENABLED          : True,
    KEY_ONLINE_MODE_ENABLED     : True,
    KEY_INCLUDE_CHANNELS        : [True] * prefs.DEFAULT_INCLUDE_COUNT,
    KEY_TRACK_VISIBILITY        : {
        "Acetaldehyde (CH\u2083CHO)": True,
        "Ammonia (NH\u2083)": True,
        "Carbon Dioxide (CO\u2082)": False,
        "Carbon Monoxide (CO)": True,
        "Ethanol (C\u2082H\u2085OH)": True,
        "Methane (CH\u2084)": True,
        "Methanol (CH\u2083OH)": True,
        "Nitrous Oxide (N\u2082O)": True,
        "Oxygen (O\u2082)": False,
        "Sulfur Dioxide (SO\u2082)": True,
        "Water Vapor (H\u2082O)": False
    },
}

# ----------------------------------------------------------------------
# Version info endpoint
# ----------------------------------------------------------------------

# Add to the top-level of your Flask app (app.py or routes.py)
from flask import jsonify
from pathlib import Path
import subprocess

def read_version_info():
    path = Path("/opt/GaseraMux/version_info.sh")
    info = {}

    # read from generated file if it exists
    if path.exists():
        for line in path.read_text().splitlines():
            if line.startswith("BUILD_"):
                key, val = line.split("=", 1)
                info[key] = val.strip().strip('"')
    else:
        info["BUILD_HASH"] = "unknown"
        info["BUILD_DATE"] = "n/a"

    # --- ensure tag field is present ---
    if "BUILD_TAG" not in info:
        try:
            # List tags pointing to the current commit
            tag = subprocess.run(
                ["git", "-C", "/opt/GaseraMux", "tag", "--points-at", "HEAD"],
                check=True, capture_output=True, text=True
            ).stdout.strip()
            info["BUILD_TAG"] = tag.splitlines()[0] if tag else "—"
        except subprocess.CalledProcessError:
            info["BUILD_TAG"] = "—"


    return info

# visible in journalctl/systemctl logs
ver = read_version_info()
info(f"[GaseraMux] Running build {ver.get('BUILD_SHORT','?')} ({ver.get('BUILD_DATE','?')})")

# API endpoint
@system_bp.route("/version/local")
def version_local():
    return jsonify(read_version_info())

from system.github_commits import get_github_commits
@system_bp.get("/version/github")
def version_github():
    stable_only = request.args.get("stable") == "1"
    force = request.args.get("force") == "1"   # ✅ correct key
    data = get_github_commits(force=force, stable_only=stable_only)
    return jsonify(data)

from flask import request, jsonify, abort
from system.version_manager import (
    require_admin, checkout_commit, rollback_previous
)

# Dummy commit for testing
@system_bp.post("/version/checkout")
def version_checkout():
    if not require_admin(request):
        abort(403)
    try:
        try:
            payload = request.get_json(force=True, silent=True) or {}
        except Exception:
            payload = {}
        sha = (payload.get("sha") or "").strip()

        result = checkout_commit(sha)
        response = jsonify({"status": "ok", **result})

        # Do not restart if nothing changed
        if not result.get("noop"):
            import threading, os, time
            def restart_service():
                time.sleep(1)
                os.system("sudo systemctl restart gasera.service")

            threading.Thread(target=restart_service, daemon=True).start()

        return response

    except Exception as e:
        warn(f"[VERSION] Checkout failed: {e}")
        return jsonify({"status": "error", "error": str(e)}), 400

@system_bp.post("/version/rollback")
def version_rollback():
    if not require_admin(request):
        abort(403)
    try:
        # Perform the rollback logic first (your existing helper)
        result = rollback_previous()

        # Prepare and send response before restarting service
        response = jsonify({"status": "ok", **result})

        import threading, os, time

        def restart_service():
            time.sleep(1.0)
            os.system("sudo systemctl restart gasera.service")

        threading.Thread(target=restart_service, daemon=True).start()

        return response

    except Exception as e:
        warn(f"[VERSION] Rollback failed: {e}")
        return jsonify({"status": "error", "error": str(e)}), 400


# ----------------------------------------------------------------------
# GET current preferences
# ----------------------------------------------------------------------
@system_bp.route("/prefs", methods=["GET"])
def get_preferences() -> tuple[Response, int]:
    """
    Returns the merged dictionary of defaults and stored prefs.
    Always includes all known keys.
    """
    merged = {**DEFAULTS, **prefs.as_dict()}
    return jsonify(merged), 200


# ----------------------------------------------------------------------
# POST updated preferences
# ----------------------------------------------------------------------
@system_bp.route("/prefs", methods=["POST"])
def update_preferences() -> tuple[Response, int]:
    """
    Updates user preferences from JSON body.
    Accepts only valid keys defined in Preferences.VALID_PREF_KEYS.
    """
    data = request.get_json(force=True)
    if not data or not isinstance(data, dict):
        return jsonify({"ok": False, "error": "Invalid JSON body"}), 400

    updated = prefs.update_from_dict(data)
    if not updated:
        return jsonify({"ok": False, "error": "No valid keys to update"}), 400

    return jsonify({"ok": True, "updated": updated}), 200


# ----------------------------------------------------------------------
# GET defaults only (optional convenience endpoint)
# ----------------------------------------------------------------------
@system_bp.route("/prefs/defaults", methods=["GET"])
def get_defaults() -> tuple[Response, int]:
    """Return the factory default preference values."""
    return jsonify(DEFAULTS), 200

# ----------------------------------------------------------------------
# GET current buzzer state
# ----------------------------------------------------------------------
@system_bp.route("/buzzer", methods=["GET"])
def get_buzzer_state() -> tuple[Response, int]:
    """
    Returns the live buzzer enable state.
    Falls back to stored preference if not yet set.
    """
    try:
        enabled = getattr(buzzer, "enabled", None)
        if enabled is None:
            enabled = prefs.get(KEY_BUZZER_ENABLED, True)
        return jsonify({"ok": True, "enabled": bool(enabled)}), 200
    except Exception as e:
        error(f"[BUZZER] get_buzzer_state error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

# ----------------------------------------------------------------------
# POST enable/disable buzzer live + persist preference
# ----------------------------------------------------------------------
@system_bp.route("/buzzer", methods=["POST"])
def set_buzzer_state() -> tuple[Response, int]:
    """
    Enables/disables buzzer immediately and persists the setting.
    Body: { "enabled": true | false }
    """
    data = request.get_json(force=True)
    if not data or "enabled" not in data:
        return jsonify({"ok": False, "error": "Missing 'enabled' field"}), 400

    enabled = bool(data["enabled"])
    try:
        # Live update
        if hasattr(buzzer, "set_enabled"):
            buzzer.set_enabled(enabled)
        else:
            buzzer.enabled = enabled

        # Persist to preferences
        prefs.update_from_dict({KEY_BUZZER_ENABLED: enabled})
        debug(f"[BUZZER] {'enabled' if enabled else 'disabled'} via POST")
        return jsonify({"ok": True, "enabled": enabled}), 200

    except Exception as e:
        error(f"[BUZZER] set_buzzer_state error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500
