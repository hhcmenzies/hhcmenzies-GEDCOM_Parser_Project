"""
exporter.py

High-level export facade for gedcom_parser.

Goals:
- Provide a stable, *simple* API for writing the registry to JSON.
- Maintain backward compatibility with older code calling
  `export_registry_to_json(registry, output_path)`.
- Route all actual work through `json_exporter.export_registry_json`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from gedcom_parser.logging import get_logger
from .json_exporter import export_registry_json

log = get_logger("exporter")


def export_registry(registry: Any, output_path: str | Path) -> None:
    """
    Preferred modern API.

    Usage:

        from gedcom_parser.exporter import export_registry

        export_registry(registry, "outputs/export.json")
    """
    path = Path(output_path)
    log.debug("export_registry called with output_path=%s", path)
    export_registry_json(registry, path)


def export_registry_to_json(*args: Any) -> None:
    """
    Backward-compatible adapter.

    Historically this function sometimes accepted:
      - export_registry_to_json(registry, output_path)

    We now standardize that as the *only* valid signature.
    Any legacy single-argument usage will raise a clear error.
    """
    if len(args) == 1:
        # Older code might have expected some global registry export.
        # We explicitly reject that now to avoid silent behavior.
        raise TypeError(
            "export_registry_to_json now requires two arguments: "
            "export_registry_to_json(registry, output_path)."
        )

    if len(args) != 2:
        raise TypeError(
            "export_registry_to_json expects exactly two arguments: "
            "(registry, output_path). Got %d." % len(args)
        )

    registry, output_path = args
    log.debug(
        "export_registry_to_json(adapter) called with output_path=%s", output_path
    )
    export_registry(registry, output_path)
