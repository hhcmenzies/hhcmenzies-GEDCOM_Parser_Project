from __future__ import annotations

from typing import List

from gedcom_parser.registry.entities import NoteEntity, GenericAttribute
from gedcom_parser.registry.utils import (
    _iter_children,
)

from gedcom_parser.identity.uuid_factory import uuid_for_pointer

def build_note(node) -> NoteEntity:
    """
    Build a NoteEntity from a GEDCOMNode with tag 'NOTE'.

    Design principles (Phase 4):
    - PURE function (no registry access, no side effects)
    - Preserve all GEDCOM data
    - Reconstruct NOTE text exactly per GEDCOM spec:
        * CONT → newline
        * CONC → inline append
    - Preserve all unmodeled/custom sub-tags as attributes
    """

    if node.tag != "NOTE":
        raise ValueError(f"Expected NOTE node, got {node.tag}")

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------
    pointer = node.pointer
    uuid = uuid_for_pointer(pointer)

    note = NoteEntity(
        uuid=uuid,
        pointer=pointer,
        text="",
        attributes=[],
    )

    # ------------------------------------------------------------------
    # Text reconstruction (GEDCOM-compliant)
    # ------------------------------------------------------------------
    parts: List[str] = []

    if node.value:
        parts.append(node.value)

    for child in _iter_children(node):
        if child.tag == "CONT":
            # Newline continuation
            parts.append("\n")
            if child.value:
                parts.append(child.value)

        elif child.tag == "CONC":
            # Inline continuation (no newline)
            if child.value:
                parts.append(child.value)

    note.text = "".join(parts)

    # ------------------------------------------------------------------
    # Preserve unmodeled child tags (no data loss)
    # ------------------------------------------------------------------
    for child in _iter_children(node):
        if child.tag in {"CONT", "CONC"}:
            continue

        note.attributes.append(
            GenericAttribute(
                tag=child.tag,
                value=child.value,
                pointer=child.pointer,
            )
        )

    return note
