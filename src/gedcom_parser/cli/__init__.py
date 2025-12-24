
"""
CLI package for gedcom_parser.

Provides the Typer application entrypoint and shared CLI utilities.
"""

from gedcom_parser.cli.app import app, main

__all__ = [
    "app",
    "main",
]
