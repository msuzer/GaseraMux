# gasera/acquisition_engine.py
from __future__ import annotations

import threading
import time

from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, Callable

from .storage_utils import get_log_directory
from system.log_utils import debug, info, warn, error
from system.display import update_measurement_state, show_run_complete, MeasurementState
from system.preferences import prefs
from gpio.pneumatic_mux import CascadedMux
from gasera.controller import gasera, TaskIDs
from buzzer.buzzer_facade import buzzer
from gasera.measurement_logger import MeasurementLogger

from system.preferences import (
    KEY_MEASUREMENT_DURATION,
    KEY_PAUSE_SECONDS,
    KEY_REPEAT_COUNT,
    KEY_INCLUDE_CHANNELS,
    KEY_ONLINE_MODE_ENABLED
    )

# Timing constants
# Pneumatics need time to settle after movement; Gasera commands also require a short delay
SWITCHING_SETTLE_TIME = 5.0
GASERA_CMD_SETTLE_TIME = 1.0

class Phase:
    IDLE = "IDLE"
    HOMING = "HOMING"
    PAUSED = "PAUSED"
    MEASURING = "MEASURING"
    SWITCHING = "SWITCHING"
    ABORTED = "ABORTED"

@dataclass
class TaskConfig:
    measure_seconds: int
    pause_seconds: int
    repeat_count: int
    include_channels: list[bool] = field(default_factory=list)

class Progress:
    def __init__(self):
        self.phase = Phase.IDLE
        self.current_channel = 0
        self.next_channel: Optional[int] = None
        self.percent = 0
        self.overall_percent = 0
        self.repeat_index = 0
        self.repeat_total: int = 0
        self.enabled_count: int = 0
        self.step_index: int = 0
        self.total_steps: int = 0
        self.elapsed_seconds: float = 0.0
        self.tt_seconds: Optional[float] = None
    
    def reset(self):
        """Reset progress state for a new measurement run."""
        self.current_channel = 0
        self.next_channel = None
        self.percent = 0
        self.overall_percent = 0
        self.repeat_index = 0
        self.step_index = 0
        self.elapsed_seconds = 0.0

class AcquisitionEngine:
    # Total available channels (2-mux cascade: 16 + 15)
    TOTAL_CHANNELS = 31
    
    def __init__(self, cmux: CascadedMux):
        self.cmux = cmux
        self._worker: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self.cfg: Optional[TaskConfig] = None
        self.progress = Progress()
        self.callbacks: list[Callable[[Progress], None]] = []
        self._last_logged_timestamp = None
        self.logger = None
        self._last_notified_vch: int = -1
        self._start_timestamp: Optional[float] = None

    # ------------------------------------------------------------------
    # Public control
    # ------------------------------------------------------------------

    def start(self) -> tuple[bool, str]:
        with self._lock:
            if self.is_running():
                warn("[ENGINE] start requested but already running")
                buzzer.play("busy")
                return False, "Measurement already running"

            self._stop_event.clear()

            # Load and validate configuration
            validation_result = self._validate_and_load_config()
            if not validation_result[0]:
                return validation_result
            
            # Apply SONL (save-on-device) preference
            self._apply_online_mode_preference()

            # Start Gasera measurement
            if not self._start_measurement():
                error("[ENGINE] Failed to Start Gasera")
                buzzer.play("error")
                return False, "Failed to start Gasera"
            
            # Reset progress state for new run
            self.progress.reset()
            
            # Initialize logging
            log_path = get_log_directory()
            self.logger = MeasurementLogger(log_path)

            # Capture timing for frontend display
            self._start_timestamp = time.time()
            self.progress.tt_seconds = self.estimate_total_time_seconds()
            self.progress.repeat_total = self.cfg.repeat_count
            self.progress.total_steps = self.cfg.repeat_count * self.progress.enabled_count

            # Start worker thread
            self._worker = threading.Thread(target=self._run_loop, daemon=True)
            self._worker.start()

            return True, "Measurement started"

    def _validate_and_load_config(self) -> tuple[bool, str]:
        """Load configuration from preferences and validate."""
        cfg = TaskConfig(
            measure_seconds=int(prefs.get(KEY_MEASUREMENT_DURATION, 100)),
            pause_seconds=int(prefs.get(KEY_PAUSE_SECONDS, 5)),
            repeat_count=int(prefs.get(KEY_REPEAT_COUNT, 1)),
        )

        include_mask = prefs.get(KEY_INCLUDE_CHANNELS, [True] * self.TOTAL_CHANNELS)
        cfg.include_channels = list(include_mask)
        self.cfg = cfg

        self.progress.enabled_count = sum(self.cfg.include_channels)
        if self.progress.enabled_count == 0:
            warn("[ENGINE] no channels enabled, skipping measurement")
            buzzer.play("invalid")
            return False, "No channels enabled"
        
        if not gasera.is_connected():
            error("[ENGINE] Gasera not connected, cannot start measurement")
            buzzer.play("error")
            return False, "Gasera not connected"
        
        return True, "Configuration valid"

    def _apply_online_mode_preference(self):
        """Apply SONL/online mode to Gasera (preference is inverted)."""
        try:
            save_on_gasera = bool(prefs.get(KEY_ONLINE_MODE_ENABLED, False))
            desired_online_mode = not save_on_gasera  # invert semantics for SONL
            resp_online = gasera.set_online_mode(desired_online_mode)
            info(f"[ENGINE] Applied SONL online_mode={'enabled' if desired_online_mode else 'disabled'} "
                 f"(save_on_gasera={'yes' if save_on_gasera else 'no'}) resp={resp_online}")
        except Exception as e:
            warn(f"[ENGINE] Failed to apply SONL mode before start: {e}")

    def stop(self):
        if self.is_running():
            self._stop_event.set()
            self._worker.join(timeout=2.0)

    def is_running(self) -> bool:
        return bool(self._worker) and self._worker.is_alive()

    def subscribe(self, cb: Callable[[Progress], None]):
        self.callbacks.append(cb)

    # ------------------------------------------------------------------
    # Internal main loop
    # ------------------------------------------------------------------

    def _run_loop(self):
        info(f"[ENGINE] start: measure={self.cfg.measure_seconds}s, pause={self.cfg.pause_seconds}s, "
            f"repeat={self.cfg.repeat_count}, enabled_channels={self.progress.enabled_count}/{self.TOTAL_CHANNELS}")
        
        try:
            for rep in range(self.cfg.repeat_count):
                if self._stop_event.is_set():
                    break
                if not self._process_repeat_cycle(rep):
                    break  # Abort requested

        except Exception as e:
            error(f"[ENGINE] run loop error: {e}")
            self.stop()
        finally:
            self._finalize_run()

    def _process_repeat_cycle(self, rep: int) -> bool:
        """Process one complete repeat across all channels. Returns False if aborted."""

        overall_steps = self.progress.enabled_count * self.cfg.repeat_count
        processed = 0
        self.progress.percent = 0
        self.progress.current_channel = 0
        self.progress.next_channel = None
        self._update_common_progress()
        self._home_mux()
        
        for vch, enabled in enumerate(self.cfg.include_channels):
            self.progress.current_channel = vch
            
            next_vch = vch + 1
            if next_vch < len(self.cfg.include_channels):
                self.progress.next_channel = next_vch
            else:
                self.progress.next_channel = None
            
            self._update_common_progress()

            if self._stop_event.is_set():
                return False

            if enabled:
                if not self._measure_channel():
                    return False
                
                processed += 1
                self._update_progress(rep, processed, overall_steps)

            is_last_enabled = (processed >= self.progress.enabled_count)
            is_final_repeat = (rep + 1 >= self.cfg.repeat_count)
            
            if is_last_enabled:
                if is_final_repeat:
                    self._set_phase(Phase.SWITCHING)
                    self._blocking_wait(1.0, notify=True)
                    debug("[ENGINE] final channel of final repeat - signaled completion")
                    break
                debug("[ENGINE] all enabled channels processed for this repeat")
                break
            
            if not self._switch_to_next_channel(enabled):
                return False
        
        self.progress.repeat_index += 1
        return True

    def _measure_channel(self) -> bool:
        self._set_phase(Phase.PAUSED)
        if not self._blocking_wait(self.cfg.pause_seconds, notify=True):
            return False

        self._set_phase(Phase.MEASURING)
        if not self._blocking_wait(self.cfg.measure_seconds, notify=True):
            warn("[ENGINE] Aborting: measurement interrupted")
            return False
        
        return True

    def _switch_to_next_channel(self, was_enabled: bool) -> bool:
        self._set_phase(Phase.SWITCHING)
        
        if was_enabled:
            buzzer.play("step")
                
        if not self._blocking_wait(SWITCHING_SETTLE_TIME, notify=True):
            return False

        self.cmux.select_next()
        return True

    def _update_progress(self, rep: int, processed: int, overall_steps: int):
        """
        Update progress after a measurement completes.
        This is the ONLY place step_index is updated - single source of truth.
        """
        progress_pct = round((processed / self.progress.enabled_count) * 100)
        self.progress.percent = progress_pct
        
        overall_progress_pct = round(((rep * self.progress.enabled_count + processed) / overall_steps) * 100)
        self.progress.overall_percent = overall_progress_pct
        
        # step_index: total completed measurements (0-based count across all repeats)
        self.progress.step_index = rep * self.progress.enabled_count + processed
        
        self._update_common_progress()
        
        debug(f"[ENGINE] progress: {progress_pct}% overall_progress: {overall_progress_pct}% step_index: {self.progress.step_index}")

    def _finalize_run(self):
        if self._stop_event.is_set():
            self._stop_event.clear()
            self._set_phase(Phase.ABORTED)
            buzzer.play("cancel")
        else:
            self._set_phase(Phase.IDLE)
            buzzer.play("completed")
            info("[ENGINE] Measurement run complete")

        self._stop_measurement()

        if self.logger:
            self.logger.close()
            self.logger = None
        
        self._start_timestamp = None
        self.progress.tt_seconds = None


    # ------------------------------------------------------------------
    # Phase handlers
    # ------------------------------------------------------------------

    def _home_mux(self):
        self._set_phase(Phase.HOMING)
        buzzer.play("home")
        self.cmux.home()
        self._blocking_wait(SWITCHING_SETTLE_TIME, notify=True)

    def _start_measurement(self) -> bool:
        resp = gasera.start_measurement(TaskIDs.DEFAULT)
        if not resp:
            error("[ENGINE] Gasera start_measurement failed")
            return False
        time.sleep(GASERA_CMD_SETTLE_TIME)
        return True

    def _blocking_wait(self, duration: float, notify: bool = True) -> bool:
        end_time = time.monotonic() + duration
        base_interval = 0.5 if duration < 10 else 1.0
        while True:
            if self._stop_event.is_set():
                return False
            now = time.monotonic()
            remaining = end_time - now
            if remaining <= 0:
                break
            if notify:
                self._update_common_progress()
                self._notify()
            # Sleep no longer than base_interval and never longer than remaining
            sleep_time = min(base_interval, remaining)
            time.sleep(sleep_time)
        return True

    def _stop_measurement(self) -> bool:
        resp = gasera.stop_measurement()
        if not resp:
            error("[ENGINE] Gasera stop_measurement failed")
            return False
        time.sleep(GASERA_CMD_SETTLE_TIME)
        return True

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def estimate_total_time_seconds(self) -> float:
        """Estimate total run time for configured measurement (used for frontend ETA display)."""
        if not self.cfg:
            return 0.0
        
        enabled_indices = [i for i, enabled in enumerate(self.cfg.include_channels) if enabled]
        if not enabled_indices:
            return 0.0

        # Total switches: from home to last enabled channel position
        total_switches = enabled_indices[-1]
        
        total_measure_time = self.progress.enabled_count * float(self.cfg.measure_seconds)
        total_pause_time = self.progress.enabled_count * float(self.cfg.pause_seconds)
        total_switch_time = float(SWITCHING_SETTLE_TIME) + (total_switches * float(SWITCHING_SETTLE_TIME))
        
        time_per_repeat = total_measure_time + total_pause_time + total_switch_time
        # Add 1s for final completion signal
        return float(self.cfg.repeat_count) * time_per_repeat + 1.0

    def _set_phase(self, phase: str):
        with self._lock:
            if self.progress.phase == phase and self._last_notified_vch == self.progress.current_channel:
                return  # no change
            self.progress.phase = phase
            self._last_notified_vch = self.progress.current_channel
        debug(f"[ENGINE] phase -> {phase}")

        # Update display and notify callbacks
        self._update_display_for_phase(phase)
        self._notify()

    def _update_display_for_phase(self, phase: str):
        """
        Update LCD/OLED display for current phase.
        Uses step_index and repeat_index directly (no recalculation).
        """
        if phase in (Phase.MEASURING, Phase.PAUSED, Phase.SWITCHING, Phase.HOMING):
            total_steps = self.cfg.repeat_count * self.progress.enabled_count
            self.progress.total_steps = total_steps
            
            # Display: +1 to show current (not completed), clamp to avoid overflow
            current_step = min(self.progress.step_index + 1, total_steps)
            current_repeat = self.progress.repeat_index + 1
            
            self._update_common_progress()
            
            update_measurement_state(MeasurementState(
                phase=phase,
                channel=self.progress.current_channel + 1,
                repeat=current_repeat,
                repeat_total=self.cfg.repeat_count,
                step=current_step,
                total_steps=total_steps,
                tt_seconds=self.progress.tt_seconds
            ))
        elif phase == Phase.IDLE:
            show_run_complete()
        elif phase == Phase.ABORTED:
            show_run_complete(True)

    def _notify(self):
        for cb in self.callbacks:
            try:
                cb(self.progress)
            except Exception as e:
                warn(f"[ENGINE] notify error: {e}")

    def _update_common_progress(self) -> None:
        self.progress.repeat_total = self.cfg.repeat_count if self.cfg else 0
        self.progress.total_steps = (self.progress.repeat_total * self.progress.enabled_count) if self.cfg else 0
        if self._start_timestamp is not None:
            self.progress.elapsed_seconds = max(0.0, time.time() - float(self._start_timestamp))

    def _extract_timestamp(self, result):
        """
        Extracts timestamp for duplicate detection.

        Gasera ACON timestamps are in UNIX epoch seconds (int/float).
        Some older firmware versions may return a string ("readable")
        timestamp. This function supports both.

        Returns:
            float epoch timestamp, or None if invalid.
        """
        if not result:
            warn("[ENGINE] Missing result object in timestamp extractor")
            return None

        ts = result.get("timestamp")

        # ------------------------------------------------------------
        # 1. UNIX epoch (Gasera primary format)
        # ------------------------------------------------------------
        if isinstance(ts, (int, float)):
            debug(f"[ENGINE] Timestamp detected as UNIX epoch: {ts}")
            return float(ts)
        # ------------------------------------------------------------
        # 2. Legacy readable timestamps (string)
        # ------------------------------------------------------------
        if isinstance(ts, str):
            s = ts.strip()

            # ISO 8601: "YYYY-MM-DDTHH:MM:SS"
            try:
                iso = s.replace(" ", "T")  # allow "YYYY-MM-DD HH..."
                dt = datetime.fromisoformat(iso)
                debug(f"[ENGINE] Timestamp parsed as ISO: {ts}")
                return dt.timestamp()
            except Exception:
                pass
            # Common format: "YYYY-MM-DD HH:MM:SS"
            try:
                dt = datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
                debug(f"[ENGINE] Timestamp parsed as YYYY-MM-DD HH:MM:SS: {ts}")
                return dt.timestamp()
            except Exception:
                pass

            warn(f"[ENGINE] Unrecognized string timestamp format: {ts!r}")
            return None

        # ------------------------------------------------------------
        # 3. Invalid timestamp type
        # ------------------------------------------------------------
        if ts is not None:
            warn(f"[ENGINE] Invalid timestamp type {type(ts).__name__}: {ts!r}")

        return None

    def _is_duplicate_live_result(self, result):
        ts = self._extract_timestamp(result)
        if ts is None:
            return True  # ignore invalid values

        if self._last_logged_timestamp == ts:
            return True  # duplicate

        # update state
        self._last_logged_timestamp = ts
        return False

    def on_live_data(self, live_data):
        """Process live data. Returns True if data was new (not duplicate), False otherwise."""
        if not live_data or not live_data.get("components"):
            return False

        if self._is_duplicate_live_result(live_data):
            return False

        if self.logger:
            self.logger.write_measurement(live_data)
        
        return True
