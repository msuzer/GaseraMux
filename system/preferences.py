import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, List
from system.log_utils import debug, info, warn, error

# --- Preference Keys ---
VALID_PREF_KEYS = [
        "measurement_duration",
        "pause_seconds",
        "repeat_count",
        "include_channels",
        "track_visibility",
        "buzzer_enabled",
        "online_mode_enabled",
    ]

KEY_MEASUREMENT_DURATION  = VALID_PREF_KEYS[0]
KEY_PAUSE_SECONDS         = VALID_PREF_KEYS[1]
KEY_REPEAT_COUNT          = VALID_PREF_KEYS[2]
KEY_INCLUDE_CHANNELS      = VALID_PREF_KEYS[3]
KEY_TRACK_VISIBILITY      = VALID_PREF_KEYS[4]
KEY_BUZZER_ENABLED        = VALID_PREF_KEYS[5]
KEY_ONLINE_MODE_ENABLED   = VALID_PREF_KEYS[6]

class Preferences:
    """
    Simple JSON-based preference store with auto-initialization
    and callback support.
    """

    DEFAULT_INCLUDE_COUNT = 31  # default number of channels to include

    def __init__(self, filename: str = "config/user_prefs.json"):
        self.file = Path(filename)
        self.data: Dict[str, Any] = {}
        self.callbacks: List[Callable[[str, Any], None]] = []
        self._load()

        # Ensure include_channels mask exists
        if KEY_INCLUDE_CHANNELS not in self.data:
            self.data[KEY_INCLUDE_CHANNELS] = [True] * self.DEFAULT_INCLUDE_COUNT
            self.save()

    # ------------------------------------------------------------------
    # Core file ops
    # ------------------------------------------------------------------

    def _load(self):
        if not self.file.exists():
            warn(f"[PREFS] file not found, will create {self.file}")
            self.data = {}
            return
        try:
            with open(self.file, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        except Exception as e:
            error(f"[PREFS] load failed: {e}")
            self.data = {}

    def save(self):
        """Public save method."""
        try:
            self.file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            error(f"[PREFS] save failed: {e}")

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def get_int(self, key: str, default: int = 0) -> int:
        try:
            return int(self.data.get(key, default))
        except Exception:
            return default

    def get_float(self, key: str, default: float = 0.0) -> float:
        try:
            return float(self.data.get(key, default))
        except Exception:
            return default

    def get_bool(self, key: str, default: bool = False) -> bool:
        value = self.data.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("1", "true", "yes", "on")
        return bool(value)

    # ------------------------------------------------------------------
    # Mutators
    # ------------------------------------------------------------------

    def set(self, key: str, value: Any):
        """Set and immediately persist a preference."""
        self.data[key] = value
        self.save()
        self._notify(key, value)

    def update_from_dict(self, d: Dict[str, Any]):
        updated = []
        for k, v in d.items():
            # accept all known keys + include_channels list
            debug(f"[PREFS] updating {k} = {v}")
            if k in VALID_PREF_KEYS:
                self.data[k] = v
                updated.append(k)
        if updated:
            self.save()
            for k in updated:
                self._notify(k, self.data[k])
        return updated

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def add_callback(self, cb: Callable[[str, Any], None]):
        """Register callback triggered on any key change."""
        self.callbacks.append(cb)

    def _notify(self, key: str, value: Any):
        for cb in self.callbacks:
            try:
                cb(key, value)
            except Exception as e:
                warn(f"[PREFS] callback error on {key}: {e}")

    # ------------------------------------------------------------------

    def as_dict(self) -> Dict[str, Any]:
        return dict(self.data)


# Singleton
prefs = Preferences()
