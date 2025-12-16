# config.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict
import pathlib

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent  # folder of config.py

@dataclass
class LogConfig:
    # One of: "SILENT", "FATAL", "CRITICAL", "ERROR", "WARN", "INFO", "DEBUG", "VERBOSE"
    level: str = "INFO"
    show_timestamp: bool = True         # print YYYY-MM-DD HH:MM:SS
    tag: str = "auto"                   # "auto" -> module:line, or fixed string
    color: bool = True                  # ANSI colors on console
    global_kv: Dict[str, Any] = field(default_factory=dict)  # always-added fields

# Edit defaults here if you like, then import log_utils (it auto-loads this).
CONFIG = LogConfig()
