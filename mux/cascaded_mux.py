# mux/cascaded_mux.py
class CascadedMux:
    def __init__(self, mux1, mux2):
        self.m1 = mux1
        self.m2 = mux2
        self._vpos = 0

    def home(self):
        self.m1.home()
        self.m2.home()
        self._vpos = 0
        return 0

    def select_next(self):
        if self._vpos < self.m1.max - 1:
            self.m1.select_next()
        else:
            self.m2.select_next()

        self._vpos += 1
        return self._vpos
