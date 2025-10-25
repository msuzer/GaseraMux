# buzzer_facade.py
import threading
import asyncio
import atexit
from .async_buzzer import AsyncBuzzer

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
    def play(self, name, repeat=1, now=False, tag=None):
        _submit(engine.play(name, repeat=repeat, now=now, tag=tag))

    def play_morse(self, text, repeat=1, now=False, tag=None, name=None):
        _submit(engine.play_morse(text, repeat=repeat, now=now, tag=tag, name=name))

    def loop(self, name_or_text, tag=None, morse=False):
        _submit(engine.loop(name_or_text, tag=tag, morse=morse))

    def cancel(self, tag_or_name):
        _submit(engine.cancel(tag_or_name))

    def stop_all(self):
        _submit(engine.stop_all())

    def shutdown(self):
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

# Export singleton
buzzer = BuzzerFacade()
init_buzzer()

atexit.register(buzzer.shutdown)
