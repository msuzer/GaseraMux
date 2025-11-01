# gasera/acquisition_engine.py
from __future__ import annotations
import threading
import time
from dataclasses import dataclass, field
from typing import Optional, Callable

from system.log_utils import info, warn, error, debug
from system.preferences import prefs
from gpio.pneumatic_mux import CascadedMux
from gasera.controller import gasera, TaskIDs
from gasera.async_timer_bank import AsyncTimerBank
from buzzer.buzzer_facade import buzzer

from system.preferences import (
    KEY_MEASUREMENT_DURATION,
    KEY_PAUSE_SECONDS,
    KEY_REPEAT_COUNT,
    KEY_INCLUDE_CHANNELS
    )

class Phase:
    IDLE = "IDLE"
    MEASURING = "MEASURING"
    PAUSED = "PAUSED"
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
        self.virtual_channel = 0
        self.repeat_index = 0
        self.percent = 0
        self.overall_percent = 0

class AcquisitionEngine:
    def __init__(self, cmux: CascadedMux):
        self.cmux = cmux
        self._worker: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self.cfg: Optional[TaskConfig] = None
        self.progress = Progress()
        self.callbacks: list[Callable[[Progress], None]] = []
        self.timers = AsyncTimerBank()
        self.total_channels = 31  # default, matches 2 mux (16 + 15)

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

            cfg = TaskConfig(
                measure_seconds=int(prefs.get(KEY_MEASUREMENT_DURATION, 100)),
                pause_seconds=int(prefs.get(KEY_PAUSE_SECONDS, 5)),
                repeat_count=int(prefs.get(KEY_REPEAT_COUNT, 1)),
            )

            include_mask = prefs.get(KEY_INCLUDE_CHANNELS, [True] * self.total_channels)
            cfg.include_channels = list(include_mask)  # make immutable copy
            self.cfg = cfg

            enabled_count = sum(self.cfg.include_channels)
            if enabled_count == 0:
                warn("[ENGINE] no channels enabled, skipping measurement")
                buzzer.play("invalid")
                return False, "No channels enabled"
            
            if not gasera.is_connected():
                warn("[ENGINE] Gasera not connected, cannot start measurement")
                buzzer.play("error")
                return False, "Gasera not connected"

            self._worker = threading.Thread(target=self._run_loop, daemon=True)
            self._worker.start()

            return True, "Measurement started"

    def stop(self):
        if self.is_running():
            self._stop_event.set()
            self._worker.join(timeout=2.0)

    def is_running(self) -> bool:
        return self._worker and self._worker.is_alive()

    def subscribe(self, cb: Callable[[Progress], None]):
        self.callbacks.append(cb)

    def get_progress(self) -> dict:
        with self._lock:
            return {
                "phase": self.progress.phase,
                "vch": self.progress.virtual_channel,
                "repeat": self.progress.repeat_index,
            }

    # ------------------------------------------------------------------
    # Internal main loop
    # ------------------------------------------------------------------

    def _run_loop(self):
        enabled_count = sum(self.cfg.include_channels)
        info(f"[ENGINE] start: measure={self.cfg.measure_seconds}s, pause={self.cfg.pause_seconds}s, "
            f"repeat={self.cfg.repeat_count}, enabled_channels={enabled_count}/{self.total_channels}")

        try:
            overall_steps = enabled_count * self.cfg.repeat_count
            self.progress.overall_percent = 0
            for rep in range(self.cfg.repeat_count):
                if self._stop_event.is_set():
                    break # exit outer loop upon stop request

                self.progress.repeat_index = rep
                self._home_mux()

                processed = 0  # counts how many enabled channels have been measured
                self.progress.percent = 0
                for vch, enabled in enumerate(self.cfg.include_channels):
                    self.progress.virtual_channel = vch

                    if self._stop_event.is_set():
                        break # exit inner loop upon stop request

                    if enabled:
                        self._set_phase(Phase.MEASURING)
                        if not self._start_measurement():
                            error("[ENGINE] Aborting: start_measurement failed")
                            self.stop()
                            break
                        if not self._wait_measurement():
                            warn("[ENGINE] Aborting: wait_measurement interrupted")
                            break
                        if not self._stop_measurement():
                            error("[ENGINE] Aborting: stop_measurement failed")
                            self.stop()
                            break

                        processed += 1

                        progress_pct = round((processed / enabled_count) * 100)
                        self.progress.percent = progress_pct
                        overall_progress_pct = round(((rep * enabled_count + processed) / overall_steps) * 100)
                        self.progress.overall_percent = overall_progress_pct
                        info(f"[ENGINE] progress: {progress_pct}% overall_progress: {overall_progress_pct}%")
                        self._set_phase(Phase.PAUSED)

                        self._pause_between()

                        if processed >= enabled_count:
                            info("[ENGINE] all enabled channels processed for this repeat")
                            break  # all enabled channels processed

                    self._advance_to_next()

        except Exception as e:
            error(f"[ENGINE] run loop error: {e}")
            self.stop()
        finally:
            if self._stop_event.is_set():
                self._set_phase(Phase.ABORTED)
                buzzer.play("cancel")
            else: # completed normally
                # self.progress.percent = 100
                self._set_phase(Phase.IDLE)
                buzzer.play("completed")
                info("[ENGINE] Measurement run complete")
            self._stop_measurement()

    # ------------------------------------------------------------------
    # Phase handlers
    # ------------------------------------------------------------------

    def _home_mux(self):
        buzzer.play("home")
        self.cmux.home()
        time.sleep(1.0)  # allow settling

    def _advance_to_next(self):
        buzzer.play("step")
        self.cmux.select_next()
        time.sleep(1.0)  # allow settling

    def _start_measurement(self) -> bool:
        resp = gasera.start_measurement(TaskIDs.DEFAULT)
        if not resp:
            warn("[ENGINE] Gasera start_measurement failed")
            return False
        time.sleep(1.0)  # allow settling
        return True

    def _wait_measurement(self) -> bool:
        """
        Waits for the measurement duration unless stop is requested.
        Returns False only if stop_event is already set (external abort).
        """
        t0 = time.monotonic()
        while time.monotonic() - t0 < self.cfg.measure_seconds:
            if self._stop_event.is_set():
                return False
            self._notify()
            time.sleep(1.0)
        return True

    def _stop_measurement(self) -> bool:
        resp = gasera.stop_measurement()
        if not resp:
            warn("[ENGINE] Gasera stop_measurement failed")
            return False
        time.sleep(1.0)
        return True

    def _pause_between(self):
        self.timers.start("pause", self.cfg.pause_seconds)
        while not self.timers.is_expired("pause"):
            if self._stop_event.is_set():
                return
            time.sleep(0.5)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_phase(self, phase: str):
        with self._lock:
            self.progress.phase = phase
        info(f"[ENGINE] phase -> {phase}")

        self._notify()

    def _notify(self):
        for cb in self.callbacks:
            try:
                cb(self.progress)
            except Exception as e:
                warn(f"[ENGINE] notify error: {e}")
