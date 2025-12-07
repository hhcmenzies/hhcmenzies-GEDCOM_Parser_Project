"""
Exporter package.

Re-exports the main JSON export entry point used by the pipeline.
"""

from __future__ import annotations

from .exporter import export_registry_to_json

__all__ = ["export_registry_to_json"]
