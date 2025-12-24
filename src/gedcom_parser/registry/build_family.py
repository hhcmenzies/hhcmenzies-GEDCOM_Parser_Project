from __future__ import annotations

from gedcom_parser.events.event import extract_events_from_record, is_event_tag
from gedcom_parser.identity.uuid_factory import uuid_for_pointer
from gedcom_parser.registry.entities import FamilyEntity, GenericAttribute
from gedcom_parser.registry.utils import (
    _child_nodes_by_tag,
    _iter_children,
    _node_to_event_dict,
)

from gedcom_parser.attachments import extract_attached_records


def build_family(node) -> FamilyEntity:
    """
    Build a FamilyEntity from a GEDCOMNode with tag 'FAM'.

    PURE FUNCTION:
      - no registry access
      - no side effects
      - no cross-entity linking

    Notes:
      - we extract OBJE into a lossless 'attachments' field on the entity (if present on entity type)
        OR store as GenericAttribute if your entity model does not yet include 'attachments'.
    """
    if getattr(node, "tag", None) != "FAM":
        raise ValueError(f"Expected FAM node, got {getattr(node, 'tag', None)}")

    pointer = getattr(node, "pointer", None)
    if not pointer:
        raise ValueError("FAM node is missing pointer")

    family = FamilyEntity(
        uuid=uuid_for_pointer(pointer),
        pointer=pointer,
    )

    # Spouses
    husb_nodes = _child_nodes_by_tag(node, "HUSB")
    wife_nodes = _child_nodes_by_tag(node, "WIFE")
    family.husband = getattr(husb_nodes[0], "pointer", None) if husb_nodes else None
    family.wife = getattr(wife_nodes[0], "pointer", None) if wife_nodes else None

    # Children
    for chil in _child_nodes_by_tag(node, "CHIL"):
        if getattr(chil, "pointer", None):
            family.children.append(chil.pointer)

    # Events
    event_record = _node_to_event_dict(node)
    family.events.extend(extract_events_from_record(event_record))

    # Notes & Sources
    for note in _child_nodes_by_tag(node, "NOTE"):
        val = getattr(note, "value", None)
        if val:
            family.notes.append(val)

    for sour in _child_nodes_by_tag(node, "SOUR"):
        ptr = getattr(sour, "pointer", None)
        if ptr:
            family.sources.append(ptr)

    # OBJE attachments (extracted only; no promotion here)
    try:
        atts = extract_attached_records(family, node, promote=False)
        if hasattr(family, "attachments"):
            # If your FamilyEntity has this field, great.
            family.attachments.extend(atts)  # type: ignore[attr-defined]
        else:
            # Otherwise keep lossless as attributes
            for a in atts:
                family.attributes.append(
                    GenericAttribute(
                        tag="OBJE",
                        value=a.file or a.title,
                        pointer=a.pointer,
                        lineno=a.raw.get("lineno"),
                    )
                )
    except Exception:
        # Do not break family building due to attachment oddities; preserve via generic attributes below.
        pass

    # Generic Attributes (lossless)
    handled_tags = {"HUSB", "WIFE", "CHIL", "NOTE", "SOUR", "OBJE"}

    for child in _iter_children(node):
        ctag = getattr(child, "tag", None)
        if not ctag:
            continue
        if ctag in handled_tags:
            continue
        if is_event_tag(ctag):
            continue

        family.attributes.append(
            GenericAttribute(
                tag=ctag,
                value=getattr(child, "value", None),
                pointer=getattr(child, "pointer", None),
                children=[
                    {"tag": getattr(c, "tag", None), "value": getattr(c, "value", None)}
                    for c in _iter_children(child)
                ],
                lineno=getattr(child, "lineno", None),
            )
        )

    return family
