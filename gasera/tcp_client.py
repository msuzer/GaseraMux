# tcp_client.py — Gasera TCP client (release build)

from __future__ import annotations

import socket
import time
import random
from threading import RLock
from typing import Optional, Callable
from system.log_utils import verbose, debug, info, warn, error

# Timing constants
COMMAND_JITTER_MAX = 0.12  # max seconds of random jitter to avoid phase-locking with device

def _hexsample(b: bytes, limit: int = 64) -> str:
    if not b:
        return "<empty>"
    s = b[:limit].hex(" ")
    return s + (" …" if len(b) > limit else "")

# -----------------------------------------------------------------------------
# Protocol constants
# -----------------------------------------------------------------------------

STX = 0x02
ETX = 0x03

# -----------------------------------------------------------------------------
# Client
# -----------------------------------------------------------------------------

class GaseraTCPClient:
    """
    Minimal, robust TCP client for Gasera devices (strict STX..ETX responses).

    Design:
      • One-shot send_command(): connect → drain → send → read → disconnect.
      • Strict STX..ETX reader with overall deadline (handles junk-before-STX and chunking).
      • Optional verbose logging controlled by ENABLE_VERBOSE_PRINTS or per-instance flag.
      • Emits connection-state changes via on_connection_change (debounced).
      • Exposes on_status_change attribute for ASTS callback compatibility (not used internally).
    """

    def __init__(self, host, port=8888, connect_timeout=2.0, io_timeout=2.0, on_connection_change: Optional[Callable[[bool], None]] = None, verbose=False):
        self.host = host
        self.port = port
        self.connect_timeout = connect_timeout
        self.io_timeout = io_timeout
        self.verbose = verbose

        # Callbacks
        self.on_connection_change = on_connection_change  # bool -> None
        self.on_status_change: Optional[Callable[[object], None]] = None  # compat (ASTS result)

        # Internals
        self._sock: Optional[socket.socket] = None
        self._lock = RLock()
        self._connected = False

    # ---- Connection management ------------------------------------------------

    def _flip_connected(self, new_state: bool) -> None:
        """Set connection state and notify only when it actually changes."""
        if self._connected == new_state:
            return
        self._connected = new_state
        cb = self.on_connection_change
        if cb:
            try:
                cb(new_state)
            except Exception as e:
                error( f"on_connection_change callback error: {e}")

    def connect(self) -> bool:
        """(Re)connect socket. Returns True on success."""
        with self._lock:
            self.disconnect()  # ensure clean start
            try:
                debug( f"Connecting to {self.host}:{self.port} ct={self.connect_timeout}s io={self.io_timeout}s")
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                # Optional keepalive (ignore if unsupported)
                try:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                except OSError:
                    pass
                sock.settimeout(self.connect_timeout)
                sock.connect((self.host, self.port))
                sock.settimeout(self.io_timeout)  # slice timeout for I/O
                self._sock = sock
                self._flip_connected(True)
                debug( "Connection successful.")
                return True
            except (socket.timeout, OSError) as e:
                warn( f"Connection failed: {e}")
                self._sock = None
                self._flip_connected(False)
                return False

    def disconnect(self) -> None:
        """Close socket if open; idempotent."""
        with self._lock:
            if self._sock:
                try:
                    self._sock.close()
                except Exception:
                    pass
                finally:
                    self._sock = None
            self._flip_connected(False)

    def is_connected(self) -> bool:
        return self._connected

    def is_online(self, timeout: float = 1.0) -> bool:
        """Lightweight reachability test (does not change this client's socket)."""
        try:
            with socket.create_connection((self.host, self.port), timeout=timeout):
                return True
        except Exception:
            return False

    # ---- I/O helpers ----------------------------------------------------------

    def _drain_stale_input(self, max_ms: int = 50) -> None:
        """
        Best-effort: clear straggler bytes so each command starts clean.
        Useful if a previous response's tail arrives late.
        """
        if not self._sock:
            return
        end = time.monotonic() + (max_ms / 1000.0)
        self._sock.setblocking(False)
        drained = bytearray()
        try:
            while time.monotonic() < end:
                try:
                    data = self._sock.recv(4096)
                    if not data:
                        break
                    drained += data
                except (BlockingIOError, InterruptedError):
                    break
                except OSError:
                    break
        finally:
            self._sock.setblocking(True)
        if drained:
            debug( f"Drained {len(drained)}B stale: {_hexsample(bytes(drained))}", verbose=self.verbose)

    def _recv_until_stx_etx(self, overall_timeout: Optional[float] = None) -> Optional[str]:
        """
        Read until a full STX..ETX frame is present.
        Returns a *string containing the full frame including STX/ETX*,
        decoded with ASCII (errors='ignore'). Returns None on timeout/error.
        """
        assert self._sock
        deadline = time.monotonic() + (overall_timeout or self.io_timeout)
        buf = bytearray()

        # small per-iteration timeout to honor overall deadline
        self._sock.settimeout(0.25)

        while time.monotonic() < deadline:
            try:
                chunk = self._sock.recv(4096)
            except socket.timeout:
                continue
            except OSError as e:
                error( f"recv OSError: {e}")
                return None

            if not chunk:
                if buf:
                    warn( "Disconnected or empty chunk")
                    debug( f"Received partial or malformed data: {_hexsample(bytes(buf))}", verbose=self.verbose)
                return None

            buf += chunk
            verbose( f"recv {len(chunk)}B: {_hexsample(chunk)} (buf={len(buf)}B)", verbose=self.verbose)

            # keep only from the *last* STX onward (discard any junk before it)
            last_stx = buf.rfind(bytes([STX]))
            if last_stx != -1:
                if last_stx > 0:
                    junk = bytes(buf[:last_stx])
                    if junk:
                        verbose( f"Discarding {len(junk)}B before STX: {_hexsample(junk)}", verbose=self.verbose)
                    del buf[:last_stx]  # STX now at buf[0]

                # find ETX after STX
                try:
                    etx_idx = buf.index(bytes([ETX]), 1)
                    frame = bytes(buf[:etx_idx + 1])  # include STX+ETX
                    payload = frame[1:-1]
                    pretty = payload.decode("ascii", errors="ignore").strip()
                    verbose( f"STX..ETX frame {len(frame)}B found (payload {len(payload)}B): '{pretty}'", verbose=self.verbose)
                    # return FULL frame so protocol.parse_response() is happy
                    return frame.decode("ascii", errors="ignore")
                except ValueError:
                    # ETX not seen yet; keep reading
                    pass

        # deadline
        if buf:
            warn( "Timeout waiting for ETX")
            debug( f"Buffer snapshot: {_hexsample(bytes(buf))}", verbose=self.verbose)
        else:
            warn( "Timeout with no data")
        return None

    # ---- Public API -----------------------------------------------------------

    def send_command(self, command: str) -> Optional[str]:
        """
        Stateless one-shot with a single quick retry on timeout/EPIPE:
          connect → drain → send → read full frame → (retry once if needed) → disconnect
        Returns the full STX..ETX framed string on success, or None on failure.
        """
        with self._lock:
            # small jitter avoids phase-locking with device internals
            time.sleep(random.uniform(0.0, COMMAND_JITTER_MAX))

            for attempt in (1, 2):
                if not self.connect():
                    if attempt == 1:
                        continue
                    return None
                try:
                    assert self._sock
                    self._drain_stale_input()
                    debug( f"Sending command: {command.strip()}", verbose=self.verbose)
                    self._sock.sendall(command.encode("ascii"))  # Gasera expects no CR/LF

                    resp = self._recv_until_stx_etx(self.io_timeout + 0.5)  # slight headroom
                    if resp is None:
                        warn( "No response or timeout occurred")
                        # retry once on the next loop iteration
                    else:
                        pretty = resp.replace(chr(STX), "").replace(chr(ETX), "").strip()
                        debug( f"Response: {pretty}", verbose=self.verbose)
                        return resp

                except (socket.timeout, BrokenPipeError, OSError) as e:
                    error( f"Communication error: {e}")
                    # fall through to retry

                finally:
                    # close every time; next loop will reconnect cleanly if retrying
                    self.disconnect()

            # both attempts failed
            return None

# Global reference (None until initialized)
tcp_client: GaseraTCPClient | None = None

def init_tcp_client(host: str, port: int = 8888):
    """Create and store a global TCP client instance."""
    global tcp_client
    tcp_client = GaseraTCPClient(host=host, port=port)
    return tcp_client