import time

class AsyncTimerBank:
    def __init__(self):
        self._timers = {}  # name -> expire_time (float)

    def start(self, name: str, delay_sec: float):
        self._timers[name] = time.monotonic() + delay_sec

    def restart(self, name: str, delay_sec: float):
        self.start(name, delay_sec)

    def stop(self, name: str):
        if name in self._timers:
            del self._timers[name]

    def is_expired(self, name: str) -> bool:
        return name in self._timers and time.monotonic() >= self._timers[name]

    def is_active(self, name: str) -> bool:
        return name in self._timers

    def time_remaining(self, name: str) -> float:
        if name in self._timers:
            return max(0.0, self._timers[name] - time.monotonic())
        return 0.0
