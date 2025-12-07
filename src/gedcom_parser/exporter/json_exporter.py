"""
json_exporter.py
Safe JSON exporter for EntityRegistry-style objects.

This module:

- Accepts the current in-memory registry object (with dict attributes).
- Produces a plain JSON-compatible dict.
- Writes it to disk with robust logging.
- Does NOT change the structure of the registry; it just serializes it.

Expected registry shape (minimal):

    registry.individuals    -> dict
    registry.families       -> dict
    registry.sources        -> dict
    registry.repositories   -> dict
    registry.media_objects  -> dict
    registry.uuid_index     -> dict (optional)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from gedcom_parser.logger import get_logger

log = get_logger("json_exporter")


def _safe_json_value(obj: Any) -> Any:
    """
    Make sure any value is JSON-serializable.

    - Passes through primitives (None, bool, int, float, str).
    - Recursively handles dict, list, tuple, set.
    - Fallback: use str(obj).

    This matches the intent of the earlier safe exporter:
    don't mutate the registry structure, just ensure we can dump it.
    """
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj

    if isinstance(obj, dict):
        return {str(k): _safe_json_value(v) for k, v in obj.items()}

    if isinstance(obj, (list, tuple, set)):
        return [_safe_json_value(v) for v in obj]

    # Fallback for any custom object (e.g., dataclasses, models)
    return str(obj)


def build_registry_dict(registry: Any) -> Dict[str, Any]:
    """
    Build the top-level dict that will be written to JSON.

    This preserves the original JSON structure:

    {
        "individuals":  { ... },
        "families":     { ... },
        "sources":      { ... },
        "repositories": { ... },
        "media_objects":{ ... },
        "uuid_index":   { ... }   # when present
    }
    """
    individuals = getattr(registry, "individuals", {}) or {}
    families = getattr(registry, "families", {}) or {}
    sources = getattr(registry, "sources", {}) or {}
    repositories = getattr(registry, "repositories", {}) or {}
    media_objects = getattr(registry, "media_objects", {}) or {}
    uuid_index = getattr(registry, "uuid_index", None)

    data: Dict[str, Any] = {
        "individuals": {
            ptr: _safe_json_value(ent) for ptr, ent in individuals.items()
        },
        "families": {
            ptr: _safe_json_value(ent) for ptr, ent in families.items()
        },
        "sources": {
            ptr: _safe_json_value(ent) for ptr, ent in sources.items()
        },
        "repositories": {
            ptr: _safe_json_value(ent) for ptr, ent in repositories.items()
        },
        "media_objects": {
            ptr: _safe_json_value(ent) for ptr, ent in media_objects.items()
        },
    }

    # uuid_index was present in your later pipeline exports – keep it when available
    if uuid_index is not None:
        data["uuid_index"] = _safe_json_value(uuid_index)

    return data


def serialize_registry_to_json_string(registry: Any, indent: int = 2) -> str:
    """
    Return a JSON string representation of the registry.

    This is a pure function (no I/O); useful for tests or callers that
    want the JSON string without writing a file.
    """
    data = build_registry_dict(registry)
    return json.dumps(data, indent=indent, ensure_ascii=False)


def export_registry_json(registry: Any, output_path: str | Path, indent: int = 2) -> None:
    """
    High-level helper: serialize the registry and write it to disk.

    This function:

    - Logs entity counts (INDI / FAM / SOUR / REPO / OBJE).
    - Creates parent directories as needed.
    - Writes UTF-8 JSON with the given indent.
    - Logs final file size in bytes.

    It is the function importer by exporter.export_registry_to_json
    and is the main I/O entry point for JSON export.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Count entities for logging
    individuals = getattr(registry, "individuals", {}) or {}
    families = getattr(registry, "families", {}) or {}
    sources = getattr(registry, "sources", {}) or {}
    repositories = getattr(registry, "repositories", {}) or {}
    media_objects = getattr(registry, "media_objects", {}) or {}

    log.info(
        "Exporting registry JSON to: %s "
        "(INDI=%d, FAM=%d, SOUR=%d, REPO=%d, OBJE=%d)",
        output_path,
        len(individuals),
        len(families),
        len(sources),
        len(repositories),
        len(media_objects),
    )

    # Serialize to string first so we can easily compute size if desired
    json_str = serialize_registry_to_json_string(registry, indent=indent)

    try:
        with output_path.open("w", encoding="utf-8") as f:
            f.write(json_str)
    except Exception:  # pragma: no cover
        log.exception("JSON export failed.")
        raise

    try:
        size_bytes = output_path.stat().st_size
    except OSError:
        size_bytes = len(json_str.encode("utf-8"))

    log.info("JSON export complete. size=%d bytes", size_bytes)
