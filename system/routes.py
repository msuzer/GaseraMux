from flask import Blueprint, jsonify, request
from system.preferences import prefs
from system.log_utils import info, warn
from system.preferences import (
    KEY_INCLUDE_CHANNELS,
    KEY_MEASUREMENT_DURATION,
    KEY_PAUSE_SECONDS,
    KEY_REPEAT_COUNT,
    KEY_TRACK_VISIBILITY)

system_bp = Blueprint("system", __name__)

# Unified default values
DEFAULTS = {
    KEY_MEASUREMENT_DURATION    : 100,
    KEY_PAUSE_SECONDS           : 5,
    KEY_REPEAT_COUNT            : 1,
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
# GET current preferences
# ----------------------------------------------------------------------
@system_bp.route("/prefs", methods=["GET"])
def get_preferences():
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
def update_preferences():
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
def get_defaults():
    """Return the factory default preference values."""
    return jsonify(DEFAULTS), 200
