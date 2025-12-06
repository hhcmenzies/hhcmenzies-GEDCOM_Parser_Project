"""
Common base class for entity wrappers.

Phase 1 – Entities backbone

This is intentionally small and conservative:
- No imports from other project modules.
- No behavioral changes to existing extractors/export.
- Safe to adopt later in IndividualEntity, FamilyEntity, etc.

It gives us:
- pointer: record XREF (e.g., "@I1@") or UUID
- root:   parsed GEDCOM node dict (as produced by tree_builder/value_reconstructor)
- meta:   free-form metadata/scoring/flags container

Helpers:
- .tag       -> top-level tag of the record
- .children  -> list of child nodes
- .to_dict() -> JSON-safe representation (no Python object cycles)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class BaseEntity:
    """
    Minimal base entity wrapper for INDI, FAM, SOUR, REPO, OBJE, etc.

    This class does NOT enforce any schema on the GEDCOM node; it simply
    wraps the raw tree node plus an optional pointer and metadata.
    """

    pointer: str | None
    root: Dict[str, Any]
    meta: Dict[str, Any] = field(default_factory=dict)

    @property
    def tag(self) -> str | None:
        """Top-level GEDCOM tag for this record (e.g., INDI, FAM, SOUR)."""
        return self.root.get("tag")

    @property
    def children(self) -> List[Dict[str, Any]]:
        """Child nodes of the underlying GEDCOM record."""
        return self.root.get("children", []) or []

    def to_dict(self) -> Dict[str, Any]:
        """
        JSON-safe representation of this entity.

        NOTE:
        - We assume `root` is a plain dict/list tree with no Python-level
          circular references (tree_builder + value_reconstructor already
          operate this way).
        - `meta` is kept shallow and JSON-serializable by callers.
        """
        return {
            "pointer": self.pointer,
            "tag": self.tag,
            "root": self.root,
            "meta": self.meta,
        }
