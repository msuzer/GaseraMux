# gasera/acquisition_engine.py
from __future__ import annotations
import threading
import time
from dataclasses import dataclass, asdict
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
    STARTING = "STARTING"
    MEASURING = "MEASURING"
    STOPPING = "STOPPING"
    PAUSED = "PAUSED"
    ADVANCING = "ADVANCING"
    COMPLETED = "COMPLETED"
    ABORTED = "ABORTED"
    ERROR = "ERROR"


@ dataclass
class TaskConfig:
    def __init__(self, measure_seconds: int, pause_seconds: int, repeat_count: int):
        self.measure_seconds = measure_seconds
        self.pause_seconds = pause_seconds
        self.repeat_count = repeat_count
        self.include_channels: list[bool] = []


class Progress:
    def __init__(self):
        self.phase = Phase.IDLE
        self.virtual_channel = 0
        self.repeat_index = 0


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

    def start(self) -> bool:
        with self._lock:
            if self._worker and self._worker.is_alive():
                warn("[ENGINE] start requested but already running")
                return False

            self._stop_event.clear()

            cfg = TaskConfig(
                measure_seconds=int(prefs.get(KEY_MEASUREMENT_DURATION, 300)),
                pause_seconds=int(prefs.get(KEY_PAUSE_SECONDS, 5)),
                repeat_count=int(prefs.get(KEY_REPEAT_COUNT, 1)),
            )

            include_mask = prefs.get(KEY_INCLUDE_CHANNELS, [True] * self.total_channels)
            cfg.include_channels = list(include_mask)  # make immutable copy
            self.cfg = cfg

            self._worker = threading.Thread(target=self._run_loop, daemon=True)
            self._worker.start()

            # info(f"[ENGINE] starting with config {asdict(cfg)}")
            info("[ENGINE] starting with config", cfg=asdict(cfg))
            buzzer.play("started")
            return True

    def stop(self):
        warn("[ENGINE] stop requested")
        buzzer.play("cancel")
        self._stop_event.set()

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
        try:
            self.cmux.home()
            self._set_phase(Phase.STARTING)

            for rep in range(self.cfg.repeat_count):
                if self._stop_event.is_set():
                    break
                self.progress.repeat_index = rep

                for vch, enabled in enumerate(self.cfg.include_channels):
                    if self._stop_event.is_set():
                        break
                    if not enabled:
                        continue

                    self.progress.virtual_channel = vch
                    self._advance_to_next()

                    self._start_measurement()
                    self._wait_measurement()
                    self._stop_measurement()

                    # Skip pause if last channel and last repeat
                    if not (rep == self.cfg.repeat_count - 1 and vch == self.total_channels - 1):
                        self._pause_between()

            self._set_phase(Phase.COMPLETED)

        except Exception as e:
            error(f"[ENGINE] run loop error: {e}")
            self._set_phase(Phase.ERROR)
        finally:
            gasera.stop_measurement()
            self._set_phase(Phase.IDLE)

    # ------------------------------------------------------------------
    # Phase handlers
    # ------------------------------------------------------------------

    def _advance_to_next(self):
        self._set_phase(Phase.ADVANCING)
        buzzer.play("triggered")
        self.cmux.select_next()

    def _start_measurement(self):
        self._set_phase(Phase.MEASURING)
        buzzer.play("measure_on")
        resp = gasera.start_measurement(TaskIDs.DEFAULT)
        if not resp:
            warn("[ENGINE] Gasera start_measurement returned None")

    def _wait_measurement(self):
        t0 = time.monotonic()
        while time.monotonic() - t0 < self.cfg.measure_seconds:
            if self._stop_event.is_set():
                return
            self._notify()
            time.sleep(1.0)  # relaxed SSE update interval

    def _stop_measurement(self):
        self._set_phase(Phase.STOPPING)
        buzzer.play("measure_off")
        gasera.stop_measurement()
        time.sleep(0.2)

    def _pause_between(self):
        self._set_phase(Phase.PAUSED)
        buzzer.play("paused")
        self.timers.start("pause", self.cfg.pause_seconds)
        while not self.timers.is_expired("pause"):
            if self._stop_event.is_set():
                return
            time.sleep(0.1)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_phase(self, phase: str):
        with self._lock:
            self.progress.phase = phase
        info(f"[ENGINE] phase -> {phase}")

        if phase == Phase.COMPLETED:
            buzzer.play("ended")
        elif phase == Phase.ERROR:
            buzzer.play("error")
        elif phase == Phase.ABORTED:
            buzzer.play("cancel")

        self._notify()

    def _notify(self):
        for cb in self.callbacks:
            try:
                cb(self.progress)
            except Exception as e:
                warn(f"[ENGINE] notify error: {e}")
