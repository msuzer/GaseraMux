# buzzer_facade.py
import threading
import asyncio
import atexit
from typing import Optional
from .async_buzzer import AsyncBuzzer
from system.preferences import prefs, KEY_BUZZER_ENABLED
from system.log_utils import debug, info, warn

# Create the async engine here
engine = AsyncBuzzer(
    u=0.1,
    rate_limits={"error": 1.0, "fatal": 5.0},
)

_loop = None
_thread = None
_ready = threading.Event()
_lock = threading.Lock()

def _loop_thread():
    global _loop
    _loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)

    async def _bootstrap():
        await engine.start()

    _loop.run_until_complete(_bootstrap())
    _ready.set()
    _loop.run_forever()

def init_buzzer(timeout: float = 3.0):
    global _thread
    with _lock:
        if _thread and _thread.is_alive() and _ready.is_set():
            return
        if not _thread or not _thread.is_alive():
            _ready.clear()
            _thread = threading.Thread(target=_loop_thread, daemon=True, name="buzzer-loop")
            _thread.start()
    if not _ready.wait(timeout=timeout):
        raise RuntimeError("Buzzer loop failed to initialize in time.")

def _ensure_loop():
    if _loop is None or not _ready.is_set():
        init_buzzer()
    if _loop.is_closed():
        with _lock:
            _ready.clear()
        init_buzzer()

def _submit(coro):
    _ensure_loop()
    return asyncio.run_coroutine_threadsafe(coro, _loop)

class BuzzerFacade:
    def __init__(self):
        # Load persisted buzzer state
        try:
            self.enabled = prefs.get(KEY_BUZZER_ENABLED, True)
            debug(f"[BUZZER] restored state: {'ENABLED' if self.enabled else 'DISABLED'}")
        except Exception as e:
            self.enabled = True
            warn(f"[BUZZER] restore failed: {e}")
        
        # Ensure event loop is ready before syncing state
        init_buzzer()
        
        # 🔧 Propagate to async engine
        try:
            if not self.enabled:
                engine.disable()
            else:
                engine.enable()
        except Exception as e:
            warn(f"[BUZZER] engine init state sync failed: {e}")

    def play(self, name: str, repeat: int = 1, now: bool = False, tag: Optional[str] = None) -> None:
        _submit(engine.play(name, repeat=repeat, now=now, tag=tag))

    def play_morse(self, text: str, repeat: int = 1, now: bool = False, tag: Optional[str] = None, name: Optional[str] = None) -> None:
        _submit(engine.play_morse(text, repeat=repeat, now=now, tag=tag, name=name))

    def loop(self, name_or_text: str, tag: Optional[str] = None, morse: bool = False) -> None:
        _submit(engine.loop(name_or_text, tag=tag, morse=morse))

    def cancel(self, tag_or_name: str) -> None:
        _submit(engine.cancel(tag_or_name))

    def stop_all(self) -> None:
        _submit(engine.stop_all())

    def shutdown(self) -> None:
        if _loop is None or not _ready.is_set():
            return
        try:
            fut = _submit(engine.shutdown())
            fut.result(timeout=2)
        except Exception:
            pass
        finally:
            try:
                _loop.call_soon_threadsafe(_loop.stop)
            except Exception:
                pass
    def set_enabled(self, state: bool) -> None:
        self.enabled = bool(state)
        if self.enabled:
            engine.enable()
        else:
            engine.disable()

    def is_enabled(self) -> bool:
        """Return current live enable state."""
        return bool(self.enabled)

# Export singleton
buzzer = BuzzerFacade()
# init_buzzer()  # Already called in BuzzerFacade.__init__
atexit.register(buzzer.shutdown)
