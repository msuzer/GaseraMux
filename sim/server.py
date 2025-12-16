import os
import socket
import threading
import time
import random
from typing import List, Tuple

# Protocol framing
STX = "\x02"
ETX = "\x03"

# Network config
HOST = "0.0.0.0"
PORT = 8888

# ---- Device status & phase maps (from user) ----
STATUS_MAP = {
    0: "initializing",
    1: "init error",
    2: "idle",
    3: "self-test",
    4: "malfunction",
    5: "measuring",
    6: "calibrating",
    7: "cancelling",
    8: "laserscan",
}

PHASE_MAP = {
    0: "Idle",
    1: "Gas exchange",
    2: "Integration",
    3: "Analysis",
    4: "Laser tuning",
}

BOOTUP_STATUS = 2  # idle

# Phase timing: total seconds for phases 1..4, evenly divided
PHASE_TOTAL_SEC = 10
PHASES = (1, 2, 3, 4)
PHASE_SLEEP = PHASE_TOTAL_SEC / len(PHASES)

# Optional dwell (pause) between cycles (seconds)
CYCLE_DWELL_SEC = 2

# Demo CAS order and simple plausible values
CAS_ORDER = ["74-82-8", "124-38-9", "7732-18-5", "10024-97-2", "7664-41-7"]  # CH₄, CO₂, H₂O, N₂O, NH₃

def _resp(func: str, err: int, data_tokens: List[str] = None) -> str:
    data_tokens = data_tokens or []
    parts = [STX, f" {func} {err}"]
    if data_tokens:
        parts.append(" " + " ".join(map(str, data_tokens)))
    parts.append(ETX)
    return "".join(parts)

class GaseraSimulator:
    """Stateful simulator matching one-request-per-connection behavior,
    with continuous measurement cycles until STPM is received.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self.device_status = BOOTUP_STATUS  # 2 (idle)
        self.meas_status = 0                # 0 (Idle)
        self.last_results: List[Tuple[int, str, float]] = []  # [(ts, cas, conc)]
        self._stop_evt = threading.Event()
        self._meas_thread = None
        # Track online mode (SONL) preference; default disabled.
        self.online_mode_enabled = False

    # --------- Helpers ---------
    def _set(self, *, ds=None, ms=None):
        with self._lock:
            if ds is not None:
                self.device_status = ds
            if ms is not None:
                self.meas_status = ms

    def _gen_results(self) -> List[Tuple[int, str, float]]:
        ts = int(time.time())
        values = {
            "74-82-8":  round(random.uniform(0.8, 1.2), 4),      # CH₄
            "124-38-9": round(random.uniform(400, 430), 4),      # CO₂
            "7732-18-5": round(random.uniform(7000, 7500), 4),    # H₂O
            "10024-97-2": round(random.uniform(0.0, 0.5), 4),     # N₂O
            "7664-41-7": round(random.uniform(0.001, 0.01), 4)   # NH₃
        }
        return [(ts, cas, values[cas]) for cas in CAS_ORDER]

    # --------- Protocol actions ---------
    def asts(self) -> str:
        with self._lock:
            return _resp("ASTS", 0, [str(self.device_status)])

    def amst(self) -> str:
        with self._lock:
            return _resp("AMST", 0, [str(self.meas_status)])

    def acon(self) -> str:
        with self._lock:
            if not self.last_results:
                return _resp("ACON", 1, [])
            tokens: List[str] = []
            for ts, cas, conc in self.last_results:
                tokens.extend([str(ts), cas, f"{conc}"])
            return _resp("ACON", 0, tokens)

    def stpm(self) -> str:
        # Signal stop; transition via cancelling to idle
        self._stop_evt.set()
        with self._lock:
            if self.device_status == 5:
                self.device_status = 7  # cancelling
        def _finalize():
            time.sleep(0.3)
            self._set(ds=2, ms=0)  # back to idle
        threading.Thread(target=_finalize, daemon=True).start()
        return _resp("STPM", 0, [])

    def _run_measurement_loop(self):
        """Continuous cycles until stop is requested."""
        try:
            while not self._stop_evt.is_set():
                for phase in PHASES:
                    if self._stop_evt.is_set():
                        return
                    self._set(ms=phase)
                    time.sleep(PHASE_SLEEP)
                # End of one cycle: produce results (updates timestamp each cycle)
                results = self._gen_results()
                with self._lock:
                    self.last_results = results
                    # remain in measuring (device_status=5); next cycle starts immediately/after dwell
                    self.meas_status = 1  # next cycle will set properly at start
                if CYCLE_DWELL_SEC > 0:
                    time.sleep(CYCLE_DWELL_SEC)
        finally:
            # On exit, set to idle if not explicitly cancelled elsewhere
            if self._stop_evt.is_set():
                self._set(ms=0)

    def stam(self, task_id: str) -> str:
        with self._lock:
            if self.device_status == 5:
                # already measuring; real device keeps running until STPM
                return _resp("STAM", 0, [])
            if self.device_status != 2:
                # only allow start from idle (simplified behavior)
                return _resp("STAM", 1, [])
            self._stop_evt.clear()
            self.device_status = 5  # measuring
            self.meas_status = 1    # start with Gas exchange

        self._meas_thread = threading.Thread(target=self._run_measurement_loop, daemon=True)
        self._meas_thread.start()
        return _resp("STAM", 0, [])

    def sonl(self, enable_token: str) -> str:
        """Simulate setting online mode (save-on-device) preference.
        Accepts '1' to enable, '0' to disable; returns success (0) always.
        """
        with self._lock:
            self.online_mode_enabled = (enable_token == '1')
        return _resp("SONL", 0, [])

# ---------- Minimal parser ----------
def parse_command(line: str):
    parts = line.strip().split()
    if not parts or len(parts[0]) < 4:
        return None, None, []
    func = parts[0][:4]
    channel = None
    data = []
    if len(parts) >= 2 and parts[1].startswith("K"):
        channel = parts[1][1:]
        data = parts[2:]
    else:
        data = parts[1:]
    return func, channel, data

# ---------- One-request-per-connection handler ----------
def handle_client(conn: socket.socket, addr, sim: GaseraSimulator):
    try:
        data = conn.recv(4096).decode(errors="ignore")
        if not data:
            return
        if STX not in data or ETX not in data:
            conn.sendall(_resp("UNKN", 1, []).encode())
            return
        start = data.find(STX)
        end = data.find(ETX, start + 1)
        payload = data[start + 1:end].strip()

        func, channel, tokens = parse_command(payload)
        if not func:
            resp = _resp("UNKN", 1, [])
        else:
            if func == "ASTS":
                resp = sim.asts()
            elif func == "AMST":
                resp = sim.amst()
            elif func == "ACON":
                resp = sim.acon()
            elif func == "STPM":
                resp = sim.stpm()
            elif func == "STAM":
                if not tokens:
                    resp = _resp("STAM", 1, [])  # missing task id
                else:
                    resp = sim.stam(tokens[0])
            elif func == "SONL":
                if not tokens:
                    resp = _resp("SONL", 1, [])  # missing argument
                else:
                    resp = sim.sonl(tokens[0])
            else:
                resp = _resp(func, 1, [])  # unsupported
        conn.sendall(resp.encode())
    finally:
        conn.close()  # short-lived connection

def start_server():
    sim = GaseraSimulator()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen(8)
        print(f"[SIMULATOR] Listening on {HOST}:{PORT} | PHASE_TOTAL_SEC={PHASE_TOTAL_SEC:.3f}s "
              f"(~{PHASE_SLEEP:.3f}s/phase) | CYCLE_DWELL_SEC={CYCLE_DWELL_SEC:.3f}s")
        while True:
            conn, addr = s.accept()
            th = threading.Thread(target=handle_client, args=(conn, addr, sim), daemon=True)
            th.start()

if __name__ == "__main__":
    start_server()