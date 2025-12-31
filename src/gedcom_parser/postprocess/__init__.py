"""
Postprocess modules for GEDCOM canonicalization (C.24.x).

NOTE:
- Keep this module *import-safe* for `python -m gedcom_parser.postprocess.<module>`.
- Do not eagerly import submodules here; it causes runpy RuntimeWarnings.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def promote_places_registry(root: Dict[str, Any]) -> Dict[str, int]:
    from .place_registry_builder import promote_places_registry as _fn
    return _fn(root)


def build_place_hierarchy(root: Dict[str, Any]) -> Dict[str, int]:
    from .place_hierarchy_builder import build_place_hierarchy as _fn
    return _fn(root)


def build_place_versions(root: Dict[str, Any], **kwargs: Any) -> Dict[str, int]:
    """
    Backward/compat convenience export name for place versioning.
    """
    from .place_version_builder import build_place_versions as _fn
    return _fn(root, **kwargs)


__all__ = [
    "promote_places_registry",
    "build_place_hierarchy",
    "build_place_versions",
]
