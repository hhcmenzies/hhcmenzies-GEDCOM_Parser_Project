"""
Logging package for ``gedcom_parser``.

Use ``get_logger(__name__)`` in modules to inherit shared handlers and write to a
module-specific log file.
"""

from .logger import (
    get_logger,
    list_active_loggers,
    log_debug,
    log_error,
    log_info,
    log_warning,
)

__all__ = [
    "get_logger",
    "list_active_loggers",
    "log_debug",
    "log_error",
    "log_info",
    "log_warning",
]
