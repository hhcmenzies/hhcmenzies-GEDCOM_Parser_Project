"""
Centralized logging engine for GEDCOM Parser
Option A – full visibility logging architecture

Provides:
- one master log (gedcom_parser.log)
- per-module logs (e.g., parser.log, xref_resolver.log, etc.)
- auto-created log directory
- rotating logs
- debug support via config
"""

from __future__ import annotations
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from gedcom_parser.config import get_config

# =====================================================================
# LOG DIRECTORY
# =====================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


# =====================================================================
# INTERNAL: Create rotating file handler
# =====================================================================

def _build_rotating_handler(log_path: Path, level: int) -> RotatingFileHandler:
    handler = RotatingFileHandler(
        log_path,
        maxBytes=5 * 1024 * 1024,   # 5MB
        backupCount=5,
        encoding="utf-8"
    )
    handler.setLevel(level)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    return handler


# =====================================================================
# LOGGER FACTORY
# =====================================================================

_LOGGER_CACHE = {}

def get_logger(name: str) -> logging.Logger:
    """
    Provides a logger for each module.

    - Always logs to the master log: gedcom_parser.log
    - Always logs to a module-specific log: <name>.log
    - Logs to console (INFO/ERROR)
    - DEBUG output only appears if config.debug = True
    """

    if name in _LOGGER_CACHE:
        return _LOGGER_CACHE[name]

    cfg = get_config()
    debug_enabled = bool(cfg.debug)

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG if debug_enabled else logging.INFO)
    logger.propagate = False  # Prevent duplicate console logs

    # ------------------------------------------
    # File: module log
    # ------------------------------------------
    module_log_file = LOG_DIR / f"{name}.log"
    module_handler = _build_rotating_handler(
        module_log_file,
        logging.DEBUG if debug_enabled else logging.INFO
    )
    logger.addHandler(module_handler)

    # ------------------------------------------
    # File: master log (gedcom_parser.log)
    # ------------------------------------------
    master_log_file = LOG_DIR / "gedcom_parser.log"
    master_handler = _build_rotating_handler(
        master_log_file,
        logging.DEBUG if debug_enabled else logging.INFO
    )
    logger.addHandler(master_handler)

    # ------------------------------------------
    # Console handler (INFO+ only)
    # ------------------------------------------
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    logger.addHandler(console)

    _LOGGER_CACHE[name] = logger
    return logger
