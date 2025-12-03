#!/usr/bin/env python3
# async_buzzer.py
# Async buzzer pattern player for Orange Pi Zero 3 (or any board),
# using YOUR gpio.dispatch(pin, "set"/"reset") calls.
#
# Features
# - Async worker (non-blocking)
# - Named patterns (many mapped via Morse)
# - Built-in Morse -> pulses converter (ITU-ish)
# - Queueing, repeat, preemption (now=True), looping states, cancel/stop
# - Rate limiting per pattern, min-silence between jobs
# - Pluggable unit 'u' (default 0.1s = 100 ms)

from __future__ import annotations
import asyncio
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Tuple, Union
from gpio.gpio_control import gpio
from gpio.pin_assignments import BUZZER_PIN
from system.log_utils import debug, info, warn

# ----------------------------- Types -----------------------------------------
Pulse = Tuple[float, float]  # (on_seconds, off_seconds)

@dataclass
class BuzzerJob:
    name: str
    pulses: List[Pulse]
    repeat: int = 1
    tag: Optional[str] = None           # for canceling groups/loops
    loop: bool = False                  # loop until canceled
    priority: int = 0                   # reserved; FIFO + preempt is typical
    inserted_at: float = field(default_factory=time.time)

# ------------------------ Morse Code Dictionary ------------------------------
# Minimal ITU-like map. You can extend easily.
MORSE_MAP: Dict[str, str] = {
    # Letters
    "A": ".-",   "B": "-...", "C": "-.-.", "D": "-..",  "E": ".",
    "F": "..-.", "G": "--.",  "H": "....", "I": "..",   "J": ".---",
    "K": "-.-",  "L": ".-..", "M": "--",   "N": "-.",   "O": "---",
    "P": ".--.", "Q": "--.-", "R": ".-.",  "S": "...",  "T": "-",
    "U": "..-",  "V": "...-", "W": ".--",  "X": "-..-", "Y": "-.--",
    "Z": "--..",
    # Digits
    "0": "-----","1": ".----","2": "..---","3": "...--","4": "....-",
    "5": ".....","6": "-....","7": "--...","8": "---..","9": "----.",
    # Punct/Extras (common)
    ".": ".-.-.-", ",": "--..--", "?": "..--..", "/": "-..-.",
    "=": "-...-",  "+": ".-.-.",  "-": "-....-",  "@": ".--.-.",
    # Prosigns can be approximated by their letters (e.g., "SK" = end of contact)
}

# ------------------------ Default Named Patterns -----------------------------
# Design note:
# - Strings are interpreted as Morse sequences (letters/words). Use upper or lower.
# - For ultra-simple “BIOS/IEC” beeps, we still use morse letters that yield the right feel:
#   e.g., "." => short tick (E); "--" => long-long (M); "..." => triple short (S).
DEFAULT_PATTERNS = {
    # Workflow
    "triggered": "A",          # .-  (distinct start cue)
    "started":   "E",          # .   (short)
    "paused":    "II",         # .. ..  (pair of doubles = repeating pause)
    "ended":     "S",          # ... (short triplet, completion)
    "warning":   "WM",         # .-- --  (attention grab: rising tone)
    "fatal":     "SOS",        # ... --- ...
    "ok":        "K",          # -.- (standard ACK)
    "beacon":    "E",          # . (heartbeat, looped)
    "failed":    "D",          # -.. (distinct, short + two short)
    "busy":      "V",          # ...- (progress indicator)
    "cancel":    "N",          # -. (abort)
    "invalid":   "F",          # ..-. (non-fatal reject)
    "error":     "ERR",        # . .-. .-.  (audible longer warning)
    "home":      "H",          # .... (four short = homing ticks)
    "step":      "G",          # --. (intermediate step)
    "completed": "CM",         # -.-.-- (completion tone)

    # System / network
    "power_on":   "EE",        # .. (double short boot)
    "shutdown":   "SK",        # ...-.- (end of contact)
    "wifi_connected": "W",     # .-- (link up)
    "wifi_disconnected": "NW", # -. .-- (negative + link)
    "ethernet_connected": "E", # . (simple)
    "ethernet_disconnected": "NE", # -. . (negative)
    "tcp_link_ok": "R",        # .-. (ready)
    "tcp_link_lost": "L",      # .-.. (lost link)

    # Device / analyzer
    "measurement_started": "M",     # -- (steady)
    "measurement_finished": "F",    # ..-. (fancy finish)
    "device_busy": "E",             # . (looped heartbeat)
    "device_fault": "SOS",          # ... --- ...

    # Service / maintenance
    "update_in_progress": "E",      # . (looped progress)
    "update_done": "K",             # -.- (ack)
    "calibration_start": "C",       # -.-. (consistent)
    "calibration_done": "R",        # .-. (ready)
}

# ----------------------------- Converter -------------------------------------
def morse_to_pulses(
    text: str,
    *,
    u: float = 0.1,
    pad_end: bool = False,
) -> List[Pulse]:
    """
    Convert text (letters/digits/punct) into buzzer pulses using Morse timing.
    - dot  = 1u ON
    - dash = 3u ON
    - gap between elements within a letter = 1u OFF
    - gap between letters = 3u OFF
    - gap between words (whitespace in text) = 7u OFF
    """
    text = text.strip()
    if not text:
        return []

    pulses: List[Pulse] = []
    words = text.split()  # split on whitespace
    for wi, word in enumerate(words):
        # word may be a sequence of letters like "SOS"
        for li, ch in enumerate(word.upper()):
            pattern = MORSE_MAP.get(ch)
            if not pattern:
                # Unknown char: skip
                continue
            # Each symbol in this letter
            for si, sym in enumerate(pattern):
                if sym == ".":
                    pulses.append((1*u, 1*u if si < len(pattern)-1 else 0.0))
                elif sym == "-":
                    pulses.append((3*u, 1*u if si < len(pattern)-1 else 0.0))
                else:
                    # ignore any accidental chars
                    continue
            # After a letter, add letter gap (3u) unless it's last letter of word
            if li < len(word) - 1:
                # ensure last off period grows to 3u. If last element already had 0,
                # add it; else extend the last off time.
                if pulses:
                    on, off = pulses[-1]
                    if off == 0.0:
                        pulses[-1] = (on, 3*u)
                    else:
                        pulses[-1] = (on, off + max(0.0, 3*u - off))
        # After a word, add word gap (7u) unless it's last word
        if wi < len(words) - 1 and pulses:
            on, off = pulses[-1]
            extra_gap = 7*u
            pulses[-1] = (on, off + extra_gap)

    # Optional end pad (silence)
    if pad_end and pulses:
        on, off = pulses[-1]
        pulses[-1] = (on, off + 3*u)
    return pulses

# ------------------------------ Engine ---------------------------------------
class AsyncBuzzer:
    """
    Buzzer pattern player that relies on user's gpio.dispatch(pin, 'set'/'reset').

    Example GPIO usage:
        buz = AsyncBuzzer(
            pin=12,
            set_fn=lambda: gpio.dispatch(12, "set"),
            reset_fn=lambda: gpio.dispatch(12, "reset"),
            u=0.1
        )

    Public API (async):
      - start(), shutdown()
      - play(name, repeat=1, now=False, tag=None)
      - play_custom(pulses, repeat=1, now=False, tag=None, name="custom")
      - play_morse(text, repeat=1, now=False, tag=None, name=None)
      - loop(name_or_text, tag=None, morse=False)
      - cancel(tag_or_name)
      - stop_all()
      - queue_size(), is_busy()
    """
    def __init__(
        self,
        *,
        u: float = 0.1,
        patterns: Optional[Dict[str, Union[str, List[Pulse]]]] = None,
        min_silence_between_jobs: float = 0.05,
        rate_limits: Optional[Dict[str, float]] = None,  # name -> min_interval_sec
    ):
        self.u = u
        self.patterns = dict(DEFAULT_PATTERNS)
        if patterns:
            self.patterns.update(patterns)
        self.min_silence_between_jobs = max(0.0, min_silence_between_jobs)
        self.rate_limits = rate_limits or {}

        # runtime state
        self._queue: "asyncio.Queue[BuzzerJob]" = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None
        self._cancel_current = asyncio.Event()
        self._busy = asyncio.Event()
        self._last_played: Dict[str, float] = {}  # name -> last start time
        self._disabled = False   # 🚫 master mute flag

    # ------------- Lifecycle -------------
    async def start(self):
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker(), name="buzzer_worker")

    async def shutdown(self):
        await self.stop_all()
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        # Failsafe off
        try:
            gpio.reset(BUZZER_PIN)
        except Exception:
            pass

    # ------------- Info -------------
    def queue_size(self) -> int:
        return self._queue.qsize()

    def is_busy(self) -> bool:
        return self._busy.is_set()

    # ------------- Pattern mgmt -------------
    def register(self, name: str, pattern: Union[str, List[Pulse]]):
        self.patterns[name] = pattern

    def register_many(self, mapping: Dict[str, Union[str, List[Pulse]]]):
        self.patterns.update(mapping)

    # ------------- Playback -------------
    async def play(
        self,
        name: str,
        *,
        repeat: int = 1,
        now: bool = False,
        tag: Optional[str] = None
    ):
        if self._disabled:
            return
        pattern = self.patterns.get(name)
        if pattern is None:
            raise KeyError(f"Unknown pattern '{name}'. Available: {sorted(self.patterns)}")

        debug(f"[BUZZER] Playing pattern '{name}'")

        # Rate limiting
        limit = self.rate_limits.get(name)
        if limit:
            last = self._last_played.get(name, 0.0)
            if (time.time() - last) < limit:
                return  # drop silently
            self._last_played[name] = time.time()

        if isinstance(pattern, str):
            pulses = morse_to_pulses(pattern, u=self.u)
        else:
            pulses = list(pattern)

        await self._enqueue_job(
            BuzzerJob(name=name, pulses=pulses, repeat=max(1, repeat), tag=tag),
            now=now
        )

    async def play_morse(
        self,
        text: str,
        *,
        repeat: int = 1,
        now: bool = False,
        tag: Optional[str] = None,
        name: Optional[str] = None
    ):
        name = name or f"morse:{text}"
        pulses = morse_to_pulses(text, u=self.u)
        await self._enqueue_job(
            BuzzerJob(name=name, pulses=pulses, repeat=max(1, repeat), tag=tag),
            now=now
        )

    async def play_custom(
        self,
        pulses: Iterable[Pulse],
        *,
        repeat: int = 1,
        now: bool = False,
        tag: Optional[str] = None,
        name: str = "custom"
    ):
        await self._enqueue_job(
            BuzzerJob(name=name, pulses=list(pulses), repeat=max(1, repeat), tag=tag),
            now=now
        )

    async def loop(
        self,
        name_or_text: str,
        *,
        tag: Optional[str] = None,
        morse: bool = False
    ):
        """Loop a named pattern or a raw Morse text until cancel(tag or name)."""
        if morse:
            pulses = morse_to_pulses(name_or_text, u=self.u)
            job = BuzzerJob(name=f"morse:{name_or_text}", pulses=pulses, repeat=1, tag=tag, loop=True)
        else:
            pattern = self.patterns.get(name_or_text)
            if pattern is None:
                raise KeyError(f"Unknown pattern '{name_or_text}'")
            pulses = morse_to_pulses(pattern, u=self.u) if isinstance(pattern, str) else list(pattern)
            job = BuzzerJob(name=name_or_text, pulses=pulses, repeat=1, tag=tag, loop=True)
        await self._enqueue_job(job, now=False)

    async def cancel(self, tag_or_name: str):
        """Cancel current job if matches tag/name and remove queued jobs with same tag/name."""
        # signal current
        if self._current_matches(tag_or_name):
            self._cancel_current.set()
        # drain & requeue others
        drained: List[BuzzerJob] = []
        try:
            while True:
                drained.append(self._queue.get_nowait())
        except asyncio.QueueEmpty:
            pass

        for j in drained:
            if not self._matches(j, tag_or_name):
                await self._queue.put(j)
            else:
                self._queue.task_done()  # drop
        await asyncio.sleep(0)  # let worker notice

    async def stop_all(self):
        """Hard stop: cancel current and clear queue."""
        self._cancel_current.set()
        # clear queue
        try:
            while True:
                self._queue.get_nowait()
                self._queue.task_done()
        except asyncio.QueueEmpty:
            pass
        # ensure buzzer off
        try:
            gpio.reset(BUZZER_PIN)
        except Exception:
            pass
        await asyncio.sleep(0)
        self._cancel_current.clear()

    def disable(self):
        self._disabled = True
        info("[BUZZER] disabled (muted)")
        try:
            gpio.reset(BUZZER_PIN)          # ensure pin reset
        except Exception:
            pass
        self._safe_async(self.stop_all())


    def enable(self):
        """Re-enable buzzer playback."""
        self._disabled = False
        info("[BUZZER] enabled")

    def is_enabled(self) -> bool:
        return not self._disabled

    # ------------- Internals -------------

    async def _enqueue_job(self, job: BuzzerJob, *, now: bool):
        if now:
            # hard preempt: cancel current and put this at head
            self._cancel_current.set()
            await asyncio.sleep(0)
            # Rebuild queue with job first
            pending: List[BuzzerJob] = [job]
            try:
                while True:
                    pending.append(self._queue.get_nowait())
            except asyncio.QueueEmpty:
                pass
            self._queue = asyncio.Queue()
            for j in pending:
                await self._queue.put(j)
            self._cancel_current.clear()
        else:
            await self._queue.put(job)

    def _matches(self, job: BuzzerJob, key: str) -> bool:
        return (job.tag == key) or (job.name == key)

    def _current_matches(self, key: str) -> bool:
        # lightweight flag; worker handles the actual comparison
        return False  # worker checks actively

    async def _worker(self):
        while True:
            job = await self._queue.get()
            self._busy.set()
            try:
                # Loop or finite repeats
                while True:
                    # perform one pass (one iteration or one loop cycle)
                    canceled = await self._run_one(job)
                    if canceled or not job.loop:
                        break
                # inter-job silence
                if self.min_silence_between_jobs > 0:
                    await asyncio.sleep(self.min_silence_between_jobs)
                # ensure off
                try:
                    gpio.reset(BUZZER_PIN)
                except Exception:
                    pass
            finally:
                self._busy.clear()
                self._queue.task_done()
                self._cancel_current.clear()

    async def _run_one(self, job: BuzzerJob) -> bool:
        """Run job for 'repeat' iterations. Returns True if canceled."""
        # Helper to see if canceled
        def canceled() -> bool:
            return self._cancel_current.is_set()

        # Run repeats
        for _ in range(max(1, job.repeat)):
            for on_sec, off_sec in job.pulses:
                if canceled():
                    return True
                # ON
                try:
                    gpio.set(BUZZER_PIN)
                except Exception:
                    # If GPIO raises, just attempt to continue off
                    pass
                await asyncio.sleep(max(0.0, on_sec))
                # OFF
                try:
                    gpio.reset(BUZZER_PIN)
                except Exception:
                    pass
                await asyncio.sleep(max(0.0, off_sec))
            if canceled():
                return True
        return False
    
    def _safe_async(self, coro):
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(coro)
        except RuntimeError:
            asyncio.run(coro)

