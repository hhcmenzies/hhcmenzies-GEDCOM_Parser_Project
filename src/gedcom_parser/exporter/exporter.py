"""
exporter.py
High-level JSON export entry point.

This module provides a stable API used by gedcom_parser.main:

    export_registry_to_json(registry, output_path)

It delegates the actual JSON construction to json_exporter.export_registry_json.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from gedcom_parser.logger import get_logger

from .json_exporter import export_registry_json

log = get_logger("exporter")


def export_registry_to_json(*args: Any, **kwargs: Any) -> None:
    """
    Backward-compatible entry point for exporting a registry to JSON.

    Supported call form (current pipeline):

        export_registry_to_json(registry, output_path)

    - 'registry' is the in-memory EntityRegistry (or compatible object).
    - 'output_path' is a str or Path.

    Any keyword arguments (e.g., indent=2) are forwarded to
    json_exporter.export_registry_json.

    The old single-argument style is no longer supported and will
    raise a clear error instead of silently doing nothing.
    """
    if len(args) == 2:
        registry, output_path = args
        output_path = Path(output_path)

        # Delegate to json_exporter
        export_registry_json(registry, output_path, **kwargs)
        return

    if len(args) == 1:
        raise NotImplementedError(
            "export_registry_to_json(output_path) without explicit registry "
            "is no longer supported. Call export_registry_to_json(registry, output_path)."
        )

    raise TypeError(
        "export_registry_to_json expects either "
        "(registry, output_path) or a single output_path argument."
    )
