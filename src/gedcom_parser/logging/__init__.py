"""
Logging package for gedcom_parser.

Exposes get_logger() from logger.py so modules can do:
    from gedcom_parser.logging import get_logger
"""

from .logger import get_logger

__all__ = ["get_logger"]
