"""
gedcom_parser.exporter package.

Provides a unified interface for exporting the in-memory registry
to JSON (and potentially other formats in the future).

Public API:

    from gedcom_parser.exporter import (
        export_registry,
        export_registry_to_json,
        export_registry_json,
    )
"""

from __future__ import annotations

from .exporter import export_registry, export_registry_to_json
from .json_exporter import export_registry_json

__all__ = [
    "export_registry",
    "export_registry_to_json",
    "export_registry_json",
]
