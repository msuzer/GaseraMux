# gasera/measurement_logger.py
import os
import csv
import uuid
from datetime import datetime

from system.log_utils import debug, info, warn


class MeasurementLogger:
    """
    Wide-format CSV logger.

    Header is created from the FIRST measurement's component list.
    Subsequent rows stick to that exact structure. Components = list of
    objects from SSE/live:
        { "label": "...", "ppm": value, "color": "...", "cas": "..." }
    """

    def __init__(self, base_dir="/data/logs"):
        os.makedirs(base_dir, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = uuid.uuid4().hex[:6].upper()
        self.filename = os.path.join(base_dir, f"gasera_log_{ts}_{suffix}.csv")

        info(f"MeasurementLogger (wide): logging to {self.filename}")

        # open file for writing (tab delimiter - universal and never conflicts with decimals)
        self.f = open(self.filename, "w", newline="")
        self.writer = csv.writer(self.f, delimiter='\t')

        # internal state
        self.header_written = False
        self.component_headers = []    # populated after first measurement

    # ------------------------------------------------------------
    # INTERNAL — Write header when we see the first measurement
    # ------------------------------------------------------------
    def _write_header_if_needed(self, components):
        """
        components is a list of dicts (from ACON/SSE):
            [
                { "label": "...", "ppm": x, "color": "...", "cas": "..." },
                ...
            ]
        """
        if self.header_written:
            return

        if not components:
            warn("[LOGGER] No components found to build CSV header")
            return

        # Grab the labels in device order
        self.component_headers = [c["label"] for c in components]

        header = ["timestamp", "phase", "channel", "repeat"] + self.component_headers
        self.writer.writerow(header)
        self.f.flush()

        self.header_written = True
        debug(f"[LOGGER] CSV header written: {header}")

    # ------------------------------------------------------------
    # PUBLIC — Write one measurement in wide format
    # ------------------------------------------------------------
    def write_measurement(self, live: dict) -> None:
        """
        live:
        {
            "timestamp": "...",
            "phase": ...,
            "channel": ...,
            "repeat": ...,
            "components": [
                { "label": "...", "ppm": x, "color": "...", "cas": "..." },
                ...
            ]
        }
        """
        if not live:
            return

        # Timestamp: prefer live.timestamp, fallback to now
        ts = live.get("timestamp") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        comps = live.get("components", [])

        if not comps:
            return

        # Ensure header exists
        self._write_header_if_needed(comps)
        if not self.header_written:
            return  # header still missing → skip

        # Build the row
        # Phase/channel/repeat: prefer live, fallback to progress snapshot
        row = [
            ts,
            live.get("phase"),          # frontend and backend both send these
            live.get("channel"),
            live.get("repeat"),
        ]

        # Add gas values in the header-defined order
        # Normalize ppm to float when possible
        def _num(v):
            try:
                return float(v)
            except Exception:
                return ""

        values_by_label = {c.get("label"): _num(c.get("ppm")) for c in comps if c and c.get("label") is not None}

        for label in self.component_headers:
            row.append(values_by_label.get(label, ""))

        debug(f"[LOGGER] Writing CSV row: {row}")

        self.writer.writerow(row)
        self.f.flush()

    # ------------------------------------------------------------
    def close(self):
        try:
            self.f.close()
            self.f = None
            self.writer = None
        except Exception as e:
            warn(f"[LOGGER] Error closing CSV file: {e}")
