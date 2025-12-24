"""
Compatibility shim for legacy imports.

Some tests/modules (and early Phase 4 builders) import:
    from gedcom_parser.tree_builder import GEDCOMNode, GEDCOMTree, build_tree

The canonical implementation lives under:
    gedcom_parser.loader.tree_builder
"""

from __future__ import annotations

# Primary canonical location (Phase 1–3)
from gedcom_parser.loader.tree_builder import GEDCOMNode, GEDCOMTree, build_tree  # noqa: F401

__all__ = ["GEDCOMNode", "GEDCOMTree", "build_tree"]
