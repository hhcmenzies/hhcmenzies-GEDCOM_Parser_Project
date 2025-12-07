"""
Compatibility wrapper around the centralized logging package.

Prefer importing from ``gedcom_parser.logging`` directly:
    from gedcom_parser.logging import get_logger
"""

from gedcom_parser.logging import (
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
