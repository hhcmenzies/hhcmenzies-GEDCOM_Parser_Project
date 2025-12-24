from __future__ import annotations

from typing import Optional, List

from ..entities import GedcomRegistry, MediaObjectEntity
from ..attachments import (
    XrefFactory,
    collect_xrefs_from_tree,
    extract_attachments,
    parse_media_object_record,
)

from .build_individual import build_individual
from .build_family import build_family
from .build_source import build_source
from .build_note import build_note


def build_registry(tree, *, debug_attachments: bool = False) -> GedcomRegistry:
    """Build a GedcomRegistry from a parsed GEDCOM tree.

    This version additionally:
      - Registers top-level OBJE records as MediaObjectEntity
      - Detects inline OBJE links under entities, promotes them to MediaObjectEntity records,
        and replaces the inline link with a pointer link in-place.
      - Extracts attachment links into entity.attachments with a context path.
    """

    registry = GedcomRegistry()

    # -------------------------------------------------------------------------
    # XREF factory (avoid collisions with existing pointers/values).
    # -------------------------------------------------------------------------
    # We collect xrefs from the entire tree (pointers + '@X@' values).
    existing_xrefs = collect_xrefs_from_tree(tree)
    xref_factory = XrefFactory(existing_xrefs, prefix="O")

    debug_lines: Optional[List[str]] = [] if debug_attachments else None

    # -------------------------------------------------------------------------
    # First pass: register top-level records.
    # -------------------------------------------------------------------------
    for node in tree.children:
        if node.tag == "INDI":
            ind = build_individual(node)
            # Attachments (and inline promotion) uses the original node structure.
            ind.attachments = extract_attachments(
                node, registry, xref_factory, debug=debug_attachments, debug_sink=debug_lines
            )
            registry.register_individual(ind)

        elif node.tag == "FAM":
            fam = build_family(node)
            fam.attachments = extract_attachments(
                node, registry, xref_factory, debug=debug_attachments, debug_sink=debug_lines
            )
            registry.register_family(fam)

        elif node.tag == "SOUR":
            src = build_source(node)
            src.attachments = extract_attachments(
                node, registry, xref_factory, debug=debug_attachments, debug_sink=debug_lines
            )
            registry.register_source(src)

        elif node.tag == "NOTE":
            note = build_note(node)
            registry.register_note(note)

        elif node.tag == "OBJE":
            media: MediaObjectEntity = parse_media_object_record(node)
            registry.register_media_object(media)
            if media.pointer:
                xref_factory.reserve(media.pointer)

    if debug_attachments and debug_lines:
        print("\n".join(debug_lines))

    return registry
