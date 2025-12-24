from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from gedcom_parser.attachments import AttachedRecord, should_promote_inline_obje
from gedcom_parser.identity.uuid_factory import uuid_for_record
from gedcom_parser.registry.build_family import build_family
from gedcom_parser.registry.build_individual import build_individual
from gedcom_parser.registry.build_media_object import build_media_object
from gedcom_parser.registry.build_note import build_note
from gedcom_parser.registry.build_source import build_source
from gedcom_parser.registry.entities import (
    GedcomRegistry,
    MediaFile,
    MediaObjectEntity,
)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def _iter_children(node: Any):
    return getattr(node, "children", []) or []


def _node_to_record_dict(node: Any) -> Dict[str, Any]:
    """
    Convert a GEDCOMNode into a minimal dict used ONLY for uuid_for_record().

    This must remain stable across runs and exports.
    """
    return {
        "tag": getattr(node, "tag", None),
        "value": getattr(node, "value", None),
        "pointer": getattr(node, "pointer", None),
        "lineno": getattr(node, "lineno", None),
        "children": [_node_to_record_dict(c) for c in _iter_children(node)],
    }


# ----------------------------------------------------------------------
# Promotion helpers
# ----------------------------------------------------------------------

def _promote_inline_attachment_to_media(
    attachment: AttachedRecord,
    *,
    obje_node: Any,
) -> MediaObjectEntity:
    """
    Create a MediaObjectEntity from an inline OBJE attachment.

    NOTE:
      - Promotion identity is derived from the OBJE node structure itself
      - pointer=None because inline OBJE has no GEDCOM pointer
    """
    record_dict = _node_to_record_dict(obje_node)
    media_uuid = uuid_for_record(record_dict)

    media = MediaObjectEntity(
        uuid=media_uuid,
        pointer=None,
        title=attachment.title,
        files=[],
        raw={
            "promoted_from": attachment.raw.get("owner_pointer"),
            "owner_type": attachment.raw.get("owner_type"),
            "lineno": attachment.raw.get("lineno"),
        },
    )

    if attachment.file:
        media.files.append(
            MediaFile(
                path=attachment.file,
                title=attachment.title,
                raw={
                    "role": attachment.role,
                    "source": "inline_OBJE",
                },
            )
        )

    return media


# ----------------------------------------------------------------------
# Step 4: Promotion pass
# ----------------------------------------------------------------------

def _promote_inline_objes(registry: GedcomRegistry, root_node: Any) -> None:
    """
    Step 4 (Promotion pass):

    - Locate original inline OBJE nodes in the tree
    - Promote qualifying inline OBJE attachments
    - Register MediaObjectEntity
    - Update AttachedRecord.media_object_id
    """

    # Index inline OBJE nodes by (container_pointer, lineno)
    obje_index: Dict[Tuple[Optional[str], Optional[int]], Any] = {}

    def index_objes(node: Any, container_pointer: Optional[str]):
        for ch in _iter_children(node):
            if getattr(ch, "tag", None) == "OBJE" and not getattr(ch, "pointer", None):
                key = (container_pointer, getattr(ch, "lineno", None))
                obje_index[key] = ch
            index_objes(ch, container_pointer)

    # Index all inline OBJE nodes under top-level records
    for top in _iter_children(root_node):
        index_objes(top, getattr(top, "pointer", None))

    def promote_on_entity(entity: Any):
        for att in getattr(entity, "attachments", []) or []:
            # Pointer-form OBJE
            if att.pointer:
                att.media_object_id = att.pointer
                continue

            # Inline OBJE
            owner_ptr = att.raw.get("owner_pointer")
            lineno = att.raw.get("lineno")
            obje_node = obje_index.get((owner_ptr, lineno))

            if not obje_node:
                continue
            if not should_promote_inline_obje(obje_node):
                continue

            media = _promote_inline_attachment_to_media(att, obje_node=obje_node)
            registry.register_media_object(media)

            att.media_object_id = media.uuid
            att.promoted = True

    for indi in registry.individuals.values():
        promote_on_entity(indi)
    for fam in registry.families.values():
        promote_on_entity(fam)
    for src in registry.sources.values():
        promote_on_entity(src)


# ----------------------------------------------------------------------
# Registry builder
# ----------------------------------------------------------------------

def build_registry(tree) -> GedcomRegistry:
    registry = GedcomRegistry()

    for node in tree.records:
        tag = getattr(node, "tag", None)

        if tag == "INDI":
            registry.register_individual(build_individual(node))

        elif tag == "FAM":
            registry.register_family(build_family(node))

        elif tag == "SOUR":
            registry.register_source(build_source(node))

        elif tag == "NOTE":
            registry.register_note(build_note(node))

        elif tag == "OBJE":
            registry.register_media_object(build_media_object(node))

    # -------------------------------
    # Phase 4.4: Relationship linking
    # -------------------------------
    from gedcom_parser.registry.link_entities import link_entities
    link_entities(registry)

    return registry

