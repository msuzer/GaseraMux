# gpio/mux.py
from __future__ import annotations
import time
from dataclasses import dataclass
from typing import Optional

from gpio.gpio_control import gpio
from system.log_utils import verbose, debug, info, warn


# ---------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------

@dataclass
class MuxPins:
    """GPIO pin names for one MUX driver."""
    home: str          # pulse → return to ch0
    select_next: str   # pulse → advance one step


@dataclass
class MuxTiming:
    """Pulse and settle times in ms."""
    pulse_ms: int = 50
    settle_ms: int = 30

# ---------------------------------------------------------
# Single-MUX driver
# ---------------------------------------------------------

class PneumaticMux:
    """Simple active-high multiplexer driver."""

    def __init__(self, name: str, pins: MuxPins,
                 timing: Optional[MuxTiming] = None,
                 max_channels: int = 16):
        self.name = name
        self.pins = pins
        self.timing = timing or MuxTiming()
        self.max_channels = max_channels
        self.position = 0

    def _delay_ms(self, ms: int):
        if ms > 0:
            time.sleep(ms / 1000.0)

    def _pulse(self, pin: str):
        gpio.set(pin)
        self._delay_ms(self.timing.pulse_ms)
        gpio.reset(pin)

    def home(self) -> int:
        self._pulse(self.pins.home)
        self._delay_ms(self.timing.settle_ms)
        self.position = 0
        return self.position

    def select_next(self) -> int:
        """
        Advance one channel.  When moving beyond max_channels-1,
        automatically home before continuing.
        """
        # advance logical counter
        next_pos = self.position + 1
        if next_pos >= self.max_channels:
            # wrapped → home first
            self.home()
            next_pos = 0
        else:
            self._pulse(self.pins.select_next)
            self._delay_ms(self.timing.settle_ms)

        self.position = next_pos
        return self.position

# ---------------------------------------------------------
# Dual-MUX abstraction
# ---------------------------------------------------------

class CascadedMux:
    """
    Two cascaded multiplexers:
      - MUX1 input 15 connected to MUX2 output.
    Provides a simple interface: home(), select_next(), get_position().
    """

    def __init__(self, mux1: PneumaticMux, mux2: PneumaticMux):
        self.mux1 = mux1
        self.mux2 = mux2
        self._virtual_index = 0  # 0..(mux1.max + mux2.max - 1)

    # --- API ---

    def home(self):
        """Home both muxes and reset combined index."""
        debug("[CMUX] homing both multiplexers")
        self.mux1.home()
        self.mux2.home()
        self._virtual_index = 0
        return self._virtual_index

    def select_next(self) -> int:
        """
        Step to the next virtual channel.
        Channels 0..(mux1.max-1) → MUX1 moves, MUX2=0.
        After that, MUX1 stays at last, MUX2 moves.
        When both reach end → home + MUX1=1.
        """
        if self._virtual_index < (self.mux1.max_channels - 1):
            # Still in first multiplexer range
            self.mux1.select_next()

        else:
            if self.mux2.position < (self.mux2.max_channels - 1):
                # Already in MUX2 range, advance it
                self.mux2.select_next()
            else:
                # End of both → wrap around
                self.home()
                # TODO: Verify in real test if we should advance MUX1 here or not
                # Currently commented out - may skip channel 0 after full cycle if uncommented
                # self.mux1.select_next()

        total_channels = self.mux1.max_channels + self.mux2.max_channels - 1
        self._virtual_index = (self._virtual_index + 1) % total_channels

        verbose("[CMUX] advanced", virtual=self._virtual_index,
             m1=self.mux1.position, m2=self.mux2.position)
        return self._virtual_index

    def get_position(self):
        """Return current virtual index and individual positions."""
        return {
            "virtual": self._virtual_index,
            "mux1": self.mux1.position,
            "mux2": self.mux2.position,
        }


# ---------------------------------------------------------
# Factory
# ---------------------------------------------------------

def build_default_cascaded_mux(
    mux1_home_pin: str,
    mux1_next_pin: str,
    mux2_home_pin: str,
    mux2_next_pin: str,
    *,
    max_channels: int = 16,
    pulse_ms: int = 50,
    settle_ms: int = 30
) -> CascadedMux:
    """Create both MUX drivers and return a ready CascadedMux."""
    timing = MuxTiming(pulse_ms=pulse_ms, settle_ms=settle_ms)

    mux1 = PneumaticMux("MUX1", MuxPins(mux1_home_pin, mux1_next_pin),
                        timing, max_channels)
    mux2 = PneumaticMux("MUX2", MuxPins(mux2_home_pin, mux2_next_pin),
                        timing, max_channels)

    debug("[CMUX] built",
         mux1_home=mux1_home_pin, mux1_next=mux1_next_pin,
         mux2_home=mux2_home_pin, mux2_next=mux2_next_pin,
         max_channels=max_channels)
    return CascadedMux(mux1, mux2)
