# mux/mux_gpio.py
import time
from mux.iface import MuxInterface
from gpio.gpio_control import gpio


class GPIOMux(MuxInterface):
    def __init__(self, home_pin, next_pin,
                 *, max_channels=16,
                 pulse_ms=50, settle_ms=30):
        self.home_pin = home_pin
        self.next_pin = next_pin
        self.max = max_channels
        self._pos = 0
        self.pulse = pulse_ms / 1000
        self.settle = settle_ms / 1000

    @property
    def position(self):
        return self._pos

    def _pulse(self, pin):
        gpio.set(pin)
        time.sleep(self.pulse)
        gpio.reset(pin)
        time.sleep(self.settle)

    def home(self):
        self._pulse(self.home_pin)
        self._pos = 0
        return self._pos

    def select_next(self):
        if self._pos + 1 >= self.max:
            return self.home()

        self._pulse(self.next_pin)
        self._pos += 1
        return self._pos
