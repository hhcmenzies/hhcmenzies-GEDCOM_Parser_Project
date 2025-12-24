"""
Base entity abstraction for GEDCOM-derived records.

Phase 1 – Entities backbone
===========================

This module defines a light-weight `BaseEntity` that can wrap the
normalized blocks produced by the extraction layer.

Design goals
------------

* Provide a consistent *shape* for entities:
    - pointer: original GEDCOM XREF (e.g., "@I1@", "@F12@", "@S3@").
    - tag:     record type ("INDI", "FAM", "SOUR", "REPO", "OBJE", ...).
    - data:    normalized dict block that is stored in the EntityRegistry.
    - raw_node: (optional) original parsed GEDCOM node (token tree dict).
    - meta:    (optional) extra metadata (line numbers, provenance, flags).

* Be conservative:
    - Do NOT move core logic here.
    - Do NOT change registry/exporter behavior.
    - Act mostly as a structured envelope plus a few convenience helpers.

Most of the "real" logic for individuals, families, etc. remains in:

    - gedcom_parser.entities.extraction.*
    - gedcom_parser.postprocess.*

Future phases (C.24.4.10 and beyond) may:
    - introduce typed subclasses (IndividualEntity, FamilyEntity, ...),
    - add richer helpers for sources/notes/UUIDs,
    - integrate directly with name/date/place normalization blocks.

For now, BaseEntity is intentionally minimal.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional


@dataclass
class BaseEntity:
    """
    Generic envelope for a normalized GEDCOM entity.

    Attributes
    ----------
    pointer:
        Original GEDCOM XREF (e.g., "@I1@", "@F12@", "@S3@").

    tag:
        GEDCOM record type tag ("INDI", "FAM", "SOUR", "REPO", "OBJE", etc.).

    data:
        Normalized dictionary as produced by the extraction layer.
        This is exactly what we store in EntityRegistry.{individuals,families,...}.

    raw_node:
        Optional original parsed GEDCOM node (token tree dict) for this entity.
        Included for debugging / advanced enrichment, but not required.

    meta:
        Miscellaneous metadata:
            - line numbers
            - source file info
            - flags used by post-processing

        Left intentionally free-form.
    """

    pointer: str
    tag: str
    data: Dict[str, Any]
    raw_node: Optional[Dict[str, Any]] = None
    meta: Dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Basic dict-like helpers
    # ------------------------------------------------------------------
    def get(self, key: str, default: Any = None) -> Any:
        """
        Convenience wrapper around self.data.get(...) so callers can treat
        BaseEntity as a slightly smarter dict.
        """
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """
        Set a field on the underlying data block.
        """
        self.data[key] = value

    def ensure_list_field(self, key: str) -> List[Any]:
        """
        Ensure that `data[key]` is a list, creating it if needed.
        Returns the list for chaining.
        """
        current = self.data.get(key)
        if current is None:
            lst: List[Any] = []
            self.data[key] = lst
            return lst
        if not isinstance(current, list):
            lst = [current]
            self.data[key] = lst
            return lst
        return current

    # ------------------------------------------------------------------
    # Sources / notes helpers (non-mandatory but convenient)
    # ------------------------------------------------------------------
    def add_source(self, source_pointer: str) -> None:
        """
        Append a source pointer to the entity's `sources` list.

        This does NOT deduplicate; caller can handle that if desired.
        """
        sources = self.ensure_list_field("sources")
        sources.append(source_pointer)

    def add_note(self, note_text: str) -> None:
        """
        Append a free-form note string to the entity's `notes` list.
        """
        notes = self.ensure_list_field("notes")
        notes.append(note_text)

    # ------------------------------------------------------------------
    # Serialization helpers
    # ------------------------------------------------------------------
    def to_dict(self, include_pointer_and_tag: bool = False) -> Dict[str, Any]:
        """
        Return the normalized data block as a plain dict.

        Parameters
        ----------
        include_pointer_and_tag:
            If True, the returned dict will include:
                "_pointer": original GEDCOM XREF
                "_tag":     record type

            This is *optional* and not currently used by the exporter,
            but is convenient for debugging or standalone serialization.
        """
        if not include_pointer_and_tag:
            return dict(self.data)

        merged: Dict[str, Any] = {
            "_pointer": self.pointer,
            "_tag": self.tag,
        }
        merged.update(self.data)
        return merged

    # ------------------------------------------------------------------
    # Factory helper
    # ------------------------------------------------------------------
    @classmethod
    def from_extracted_block(
        cls,
        pointer: str,
        tag: str,
        block: Dict[str, Any],
        raw_node: Optional[Dict[str, Any]] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> "BaseEntity":
        """
        Construct a BaseEntity from an already-normalized block.

        This is a thin wrapper intended for use in the extraction layer
        and registry builder. It does not modify `block` beyond storing
        it as-is in `data`.
        """
        return cls(
            pointer=pointer,
            tag=tag,
            data=dict(block),  # shallow copy for safety
            raw_node=raw_node,
            meta=dict(meta or {}),
        )
