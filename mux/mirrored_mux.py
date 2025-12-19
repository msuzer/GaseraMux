# mux/mirrored_mux.py
from mux.iface import MuxInterface

class MirroredMux(MuxInterface):
    """
    A logical mux that drives multiple physical muxes
    simultaneously (GPIO + RS232, etc).
    """

    def __init__(self, *muxes: MuxInterface):
        if not muxes:
            raise ValueError("At least one mux required")
        self._muxes = muxes

    @property
    def position(self):
        # all must be in sync; trust the first
        return self._muxes[0].position

    def home(self) -> int:
        pos = None
        for m in self._muxes:
            pos = m.home()
        return pos

    def select_next(self) -> int:
        pos = None
        for m in self._muxes:
            pos = m.select_next()
        return pos
