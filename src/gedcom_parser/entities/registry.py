"""
Entity registry compatibility layer.

Phase 4.4+

This module exists ONLY to preserve backwards compatibility with
earlier tests and modules that import:

    from gedcom_parser.entities.registry import build_entity_registry

The canonical registry implementation now lives in:

    gedcom_parser.registry.build_registry

Design principles:
- No duplicated registry logic
- No dict-based extraction
- No direct knowledge of GEDCOMNode internals
- Clean delegation to Phase 4 registry wiring
"""

from __future__ import annotations

from typing import Any, Iterable

from gedcom_parser.registry.build_registry import build_registry
from gedcom_parser.registry.entities import GedcomRegistry


def build_entity_registry(tree_or_nodes: Iterable[Any]) -> GedcomRegistry:
    """
    Backwards-compatible wrapper used by legacy tests and modules.

    Parameters
    ----------
    tree_or_nodes:
        Either:
        - GEDCOMTree (preferred)
        - Iterable of top-level GEDCOMNode records

    Returns
    -------
    GedcomRegistry
        Fully populated registry containing individuals, families,
        sources, and notes.

    Notes
    -----
    - This function intentionally contains NO logic.
    - All entity extraction and wiring is delegated to the
      Phase 4 registry builder.
    """
    return build_registry(tree_or_nodes)
