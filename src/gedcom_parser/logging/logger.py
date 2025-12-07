"""
Centralized logging configuration for the GEDCOM Parser project.

Key behaviors
-------------
* Single entry point via ``get_logger`` to keep handlers/formatters consistent.
* Master log file (default: ``logs/gedcom_parser.log``) plus per-module logs.
* Console logging that respects the configured debug flag.
* Optional log rotation controlled by ``config/gedcom_parser.yml``.
"""

from __future__ import annotations

import logging
from logging import Logger, StreamHandler
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Dict, List

from gedcom_parser.config import get_config

# -----------------------------------------------------------------------------
# Paths and configuration
# -----------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOG_DIR = PROJECT_ROOT / "logs"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Cache so handlers are only created once per module
_logger_cache: Dict[str, Logger] = {}
_base_configured: bool = False
_effective_level: int = logging.INFO
_log_dir: Path = DEFAULT_LOG_DIR
_master_log_name: str = "gedcom_parser.log"
_rotate_logs: bool = False


# -----------------------------------------------------------------------------
# Internal helpers
# -----------------------------------------------------------------------------

def _ensure_log_dir() -> Path:
    """Resolve and create the log directory from configuration."""
    global _log_dir
    cfg = get_config()

    log_dir_cfg = cfg.logging.get("dir") or cfg.paths.get("logs_dir") or "logs"
    log_dir = Path(log_dir_cfg)
    if not log_dir.is_absolute():
        log_dir = PROJECT_ROOT / log_dir

    log_dir.mkdir(parents=True, exist_ok=True)
    _log_dir = log_dir
    return log_dir


def _build_file_handler(path: Path, level: int) -> logging.Handler:
    """Create a file handler with optional rotation."""
    if _rotate_logs:
        handler = RotatingFileHandler(
            path,
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
    else:
        handler = logging.FileHandler(path, encoding="utf-8")

    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    return handler


def _configure_base_logger() -> Logger:
    """Configure the shared base logger once."""
    global _base_configured, _effective_level, _master_log_name, _rotate_logs

    if _base_configured:
        return logging.getLogger("gedcom_parser")

    cfg = get_config()
    _rotate_logs = bool(cfg.logging.get("rotate", False))
    _master_log_name = cfg.logging.get("file", "gedcom_parser.log")

    level_name = str(cfg.logging.get("level", "INFO")).upper()
    base_level = getattr(logging, level_name, logging.INFO)
    debug_enabled = bool(getattr(cfg, "debug", False))

    _effective_level = logging.DEBUG if debug_enabled else base_level

    log_dir = _ensure_log_dir()
    base_logger = logging.getLogger("gedcom_parser")
    base_logger.setLevel(_effective_level)
    base_logger.propagate = False

    # Master log handler
    master_path = log_dir / _master_log_name
    base_logger.addHandler(_build_file_handler(master_path, _effective_level))

    # Console handler
    console = StreamHandler()
    console.setLevel(logging.DEBUG if debug_enabled else logging.INFO)
    console.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    base_logger.addHandler(console)

    _base_configured = True
    return base_logger


def _module_handler_exists(logger: Logger) -> bool:
    return any(getattr(h, "is_module_handler", False) for h in logger.handlers)


def _attach_module_handler(logger: Logger, module_name: str) -> None:
    log_dir = _ensure_log_dir()
    filename = f"{module_name.replace('.', '_')}.log"
    path = log_dir / filename

    handler = _build_file_handler(path, _effective_level)
    handler.is_module_handler = True  # type: ignore[attr-defined]
    logger.addHandler(handler)


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------

def get_logger(name: str | None = None) -> Logger:
    """Return a logger configured with project-wide handlers.

    * Module loggers inherit the base console + master log handlers.
    * Each module also gains its own file handler: ``logs/<module>.log``.
    * The debug flag in ``config/gedcom_parser.yml`` forces DEBUG level output.
    """

    base_logger = _configure_base_logger()
    logger_name = name or __name__
    logger = logging.getLogger(logger_name)
    logger.setLevel(_effective_level)

    if logger_name != base_logger.name:
        if not _module_handler_exists(logger):
            _attach_module_handler(logger, logger_name)
        logger.propagate = True
    else:
        # Base logger already owns the master + console handlers
        logger.propagate = False

    _logger_cache[logger_name] = logger
    return logger


def _root_logger() -> Logger:
    return get_logger("gedcom_parser")


def log_debug(message: str, *args, **kwargs) -> None:
    _root_logger().debug(message, *args, **kwargs)


def log_info(message: str, *args, **kwargs) -> None:
    _root_logger().info(message, *args, **kwargs)


def log_warning(message: str, *args, **kwargs) -> None:
    _root_logger().warning(message, *args, **kwargs)


def log_error(message: str, *args, **kwargs) -> None:
    _root_logger().error(message, *args, **kwargs)


def list_active_loggers() -> List[str]:
    """Helper for debugging configuration issues in tests."""
    return list(_logger_cache.keys())
