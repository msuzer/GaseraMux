# log_utils.py
from __future__ import annotations
import logging, sys, time
from typing import Any, Dict, Optional
from .config import PROJECT_ROOT
import pathlib
from .config import CONFIG  # single source of truth

# ---------- Levels ----------
SILENT   = 100
FATAL    = 60
CRITICAL = 50
ERROR    = 40
WARN     = 30
INFO     = 20
DEBUG    = 10
VERBOSE  = 5

logging.addLevelName(FATAL,   "FATAL")
logging.addLevelName(VERBOSE, "VERBOSE")

_LEVEL_BY_NAME = {
    "SILENT": SILENT, "FATAL": FATAL, "CRITICAL": CRITICAL,
    "ERROR": ERROR, "WARN": WARN, "WARNING": WARN,
    "INFO": INFO, "DEBUG": DEBUG, "VERBOSE": VERBOSE,
}

def _parse_level(val: int | str) -> int:
    if isinstance(val, int): return val
    return _LEVEL_BY_NAME.get(str(val).upper(), INFO)

# ---------- Internal state (driven by CONFIG) ----------
_state = {
    "level": _parse_level(CONFIG.level),
    "show_timestamp": CONFIG.show_timestamp,
    "tag": CONFIG.tag,
    "color": CONFIG.color,
}
_GLOBAL_KV: Dict[str, Any] = dict(CONFIG.global_kv)

# ---------- Formatter ----------
class _Formatter(logging.Formatter):
    _RESET = "\x1b[0m"
    _COLORS = {
        FATAL:    "\x1b[95m",
        CRITICAL: "\x1b[35m",
        ERROR:    "\x1b[31m",
        WARN:     "\x1b[33m",
        INFO:     "\x1b[32m",
        DEBUG:    "\x1b[34m",
        VERBOSE:  "\x1b[90m",
    }

    def format(self, record: logging.LogRecord) -> str:
        lvl = record.levelno
        if _state["level"] == SILENT or lvl < _state["level"]:
            return ""

        # datetime: YYYY-MM-DD HH:MM:SS (24h)
        ts = ""
        if _state["show_timestamp"]:
            t = time.localtime(record.created)
            ts = time.strftime("%Y-%m-%d %H:%M:%S ", t)

        # tag: "auto" -> module:line or fixed string
        tag = _state["tag"]
        if tag == "auto":
            #tag = f"{record.module}:{record.lineno}" # e.g., main:42
            #tag = f"{record.filename}:{record.lineno}"  # e.g., main.py:42
            try:
                relpath = pathlib.Path(record.pathname).resolve().relative_to(PROJECT_ROOT)
            except Exception:
                relpath = pathlib.Path(record.pathname).name  # fallback to filename
            tag = f"{relpath}:{record.lineno}"

        level_name = logging.getLevelName(lvl)
        msg = record.getMessage()

        # merge context
        extra_kv = getattr(record, "_kv", {})
        merged = {**_GLOBAL_KV, **extra_kv}
        ctx = (" " + " ".join(f"{k}={merged[k]!r}" for k in sorted(merged))) if merged else ""

        line = f"{ts}{level_name:<8} [{tag}] {msg}{ctx}"

        if _state["color"]:
            color = self._COLORS.get(lvl)
            if color:
                line = f"{color}{line}{self._RESET}"

        return line

class _NonEmpty(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return True  # skipping is handled by formatter returning ""

# ---------- Singleton wiring ----------
_root = logging.getLogger("app")
_root.setLevel(VERBOSE)
_root.propagate = False
if not _root.handlers:
    h = logging.StreamHandler(stream=sys.stdout)  # console sink
    h.setLevel(VERBOSE)
    h.addFilter(_NonEmpty())
    h.setFormatter(_Formatter())
    _root.addHandler(h)

# ---------- Emit ----------
def _emit(level: int, msg: str, *, stacklevel: int = 2, **kv: Any) -> str:
    if _state["level"] == SILENT or level < _state["level"]:
        return msg
    logger = logging.getLogger("app")
    logger.log(level, msg, extra={"_kv": kv}, stacklevel=stacklevel + 1)

    if kv:
        extras = " ".join(f"{k}={v!r}" for k, v in kv.items())
        return f"{msg} {extras}"
    return msg

# ---------- Public API ----------
def reload_from_config() -> None:
    """Re-read CONFIG and apply to the singleton."""
    _state["level"] = _parse_level(CONFIG.level)
    _state["show_timestamp"] = CONFIG.show_timestamp
    _state["tag"] = CONFIG.tag
    _state["color"] = CONFIG.color
    _GLOBAL_KV.clear()
    _GLOBAL_KV.update(CONFIG.global_kv or {})

def set_level(level: int | str) -> None:
    _state["level"] = _parse_level(level)

def enable_timestamp(on: bool = True) -> None:
    _state["show_timestamp"] = bool(on)

def set_tag(tag: str) -> None:
    """'auto' for module:line, or a fixed string."""
    _state["tag"] = tag

def set_color(on: bool = True) -> None:
    _state["color"] = bool(on)

def set_global(**kv: Any) -> None:
    _GLOBAL_KV.update(kv)

def clear_global(*keys: str) -> None:
    if not keys:
        _GLOBAL_KV.clear()
    else:
        for k in keys: _GLOBAL_KV.pop(k, None)

# Levels (per-call optional sound= pattern override)
def verbose(msg: str, **kv: Any) -> str: return _emit(VERBOSE,  msg, **kv)
def debug(msg: str,   **kv: Any) -> str: return _emit(DEBUG,    msg, **kv)
def info(msg: str,    **kv: Any) -> str: return _emit(INFO,     msg, **kv)
def warn(msg: str,    **kv: Any) -> str: return _emit(WARN,     msg, **kv)
def error(msg: str,   **kv: Any) -> str: return _emit(ERROR,    msg, **kv)
def critical(msg: str, **kv: Any) -> str: return _emit(CRITICAL, msg, **kv)
def fatal(msg: str,   **kv: Any) -> str: return _emit(FATAL,    msg, **kv)

# Apply CONFIG immediately on import
reload_from_config()
