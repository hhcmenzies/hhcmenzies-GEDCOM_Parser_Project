from __future__ import annotations

from typing import Any, Dict, Optional

from gedcom_parser.attachments import extract_obje_attachments
from gedcom_parser.events.event import extract_events_from_record, is_event_tag
from gedcom_parser.identity.uuid_factory import uuid_for_pointer
from gedcom_parser.registry.entities import IndividualEntity, NameRecord, GenericAttribute


def _iter_children(node):
    return getattr(node, "children", []) or []


def _child_nodes_by_tag(node, tag: str):
    return [c for c in _iter_children(node) if getattr(c, "tag", None) == tag]


def _first_child_value(node, tag: str) -> Optional[str]:
    for c in _iter_children(node):
        if getattr(c, "tag", None) == tag:
            return getattr(c, "value", None)
    return None


def _node_to_event_dict(node) -> Dict[str, Any]:
    return {
        "tag": getattr(node, "tag", None),
        "value": getattr(node, "value", None),
        "pointer": getattr(node, "pointer", None),
        "lineno": getattr(node, "lineno", None),
        "children": [_node_to_event_dict(c) for c in _iter_children(node)],
    }


def build_individual(node) -> IndividualEntity:
    if getattr(node, "tag", None) != "INDI":
        raise ValueError(f"Expected INDI node, got {getattr(node, 'tag', None)}")

    pointer = getattr(node, "pointer", None)
    if not pointer:
        raise ValueError("INDI node is missing pointer")

    individual = IndividualEntity(
        uuid=uuid_for_pointer(pointer),
        pointer=pointer,
    )

    # Names
    for name_node in _child_nodes_by_tag(node, "NAME"):
        name = NameRecord(
            full=getattr(name_node, "value", None) or "",
            given=_first_child_value(name_node, "GIVN"),
            surname=_first_child_value(name_node, "SURN"),
            prefix=_first_child_value(name_node, "NPFX"),
            suffix=_first_child_value(name_node, "NSFX"),
            nickname=_first_child_value(name_node, "NICK"),
            name_type=_first_child_value(name_node, "TYPE"),
        )
        for sub in _iter_children(name_node):
            stag = getattr(sub, "tag", None)
            if stag and stag not in {"GIVN", "SURN", "NPFX", "NSFX", "NICK", "TYPE"}:
                name.raw[stag] = getattr(sub, "value", None)
        individual.names.append(name)

    # Gender
    individual.gender = _first_child_value(node, "SEX")

    # Family Links
    for fams in _child_nodes_by_tag(node, "FAMS"):
        ptr = getattr(fams, "pointer", None)
        if ptr:
            individual.families_as_spouse.append(ptr)

    for famc in _child_nodes_by_tag(node, "FAMC"):
        ptr = getattr(famc, "pointer", None)
        if ptr:
            individual.families_as_child.append(ptr)

    # Events
    individual.events.extend(extract_events_from_record(_node_to_event_dict(node)))

    # Notes & Sources
    for note in _child_nodes_by_tag(node, "NOTE"):
        val = getattr(note, "value", None)
        if val:
            individual.notes.append(val)

    for sour in _child_nodes_by_tag(node, "SOUR"):
        ptr = getattr(sour, "pointer", None)
        if ptr:
            individual.sources.append(ptr)

    # Attachments (Step 3 extraction only; Step 4 promotion happens in build_registry)
    individual.attachments.extend(
        extract_obje_attachments(
            node,
            origin={"container": "INDI", "pointer": node.pointer, "lineno": getattr(node, "lineno", None)},
        )
    )

    # Generic Attributes
    handled_tags = {"NAME", "SEX", "FAMS", "FAMC", "NOTE", "SOUR", "OBJE"}

    for child in _iter_children(node):
        ctag = getattr(child, "tag", None)
        if not ctag or ctag in handled_tags:
            continue
        if is_event_tag(ctag):
            continue

        individual.attributes.append(
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

    return individual
