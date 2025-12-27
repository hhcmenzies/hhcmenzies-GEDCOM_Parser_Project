"""
json_exporter.py
Structured JSON exporter for EntityRegistry-style objects.

This exporter:
- Converts dataclasses and objects to dictionaries (NOT strings)
- Preserves full structure for downstream processing
- Is safe, deterministic, and lossless
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict
from dataclasses import is_dataclass, asdict

from gedcom_parser.logger import get_logger

log = get_logger("json_exporter")


def _to_json_compatible(obj: Any) -> Any:
    """
    Recursively convert objects into JSON-compatible structures.

    Rules:
    - Primitives pass through
    - dataclasses → dict (recursively)
    - dict → dict (recursively)
    - list / tuple / set → list (recursively)
    - Unknown objects → __dict__ if present, else str(obj)
    """
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj

    if is_dataclass(obj):
        return {k: _to_json_compatible(v) for k, v in asdict(obj).items()}

    if isinstance(obj, dict):
        return {str(k): _to_json_compatible(v) for k, v in obj.items()}

    if isinstance(obj, (list, tuple, set)):
        return [_to_json_compatible(v) for v in obj]

    # Fallback: try object's __dict__
    if hasattr(obj, "__dict__"):
        return {k: _to_json_compatible(v) for k, v in obj.__dict__.items()}

    # Last resort
    return str(obj)


def build_registry_dict(registry: Any) -> Dict[str, Any]:
    """
    Convert the in-memory registry into a JSON-safe dict.
    """
    return {
        "individuals": {
            ptr: _to_json_compatible(ent)
            for ptr, ent in (getattr(registry, "individuals", {}) or {}).items()
        },
        "families": {
            ptr: _to_json_compatible(ent)
            for ptr, ent in (getattr(registry, "families", {}) or {}).items()
        },
        "sources": {
            ptr: _to_json_compatible(ent)
            for ptr, ent in (getattr(registry, "sources", {}) or {}).items()
        },
        "repositories": {
            ptr: _to_json_compatible(ent)
            for ptr, ent in (getattr(registry, "repositories", {}) or {}).items()
        },
        "media_objects": {
            ptr: _to_json_compatible(ent)
            for ptr, ent in (getattr(registry, "media_objects", {}) or {}).items()
        },
        **(
            {"uuid_index": _to_json_compatible(registry.uuid_index)}
            if hasattr(registry, "uuid_index") and registry.uuid_index
            else {}
        ),
    }


def serialize_registry_to_json_string(registry: Any, indent: int = 2) -> str:
    return json.dumps(
        build_registry_dict(registry),
        indent=indent,
        ensure_ascii=False,
    )


def export_registry_json(registry: Any, output_path: str | Path, indent: int = 2) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

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

    json_str = serialize_registry_to_json_string(registry, indent=indent)

    with output_path.open("w", encoding="utf-8") as f:
        f.write(json_str)

    size_bytes = output_path.stat().st_size
    log.info("JSON export complete. size=%d bytes", size_bytes)
