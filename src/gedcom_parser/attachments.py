from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ==============================================================================
# Models
# ==============================================================================

@dataclass(slots=True)
class AttachedRecord:
    """
    Represents an OBJE attachment encountered inside an entity record.

    - pointer: pointer-form OBJE (@O1@)
    - file: inline FILE path if present
    - title: TITL if present
    - role: reserved for future use
    - promoted: set True if promotion created a MediaObjectEntity
    - media_object_id: pointer (for pointer OBJE) or UUID (for promoted inline)
    """
    pointer: Optional[str] = None
    file: Optional[str] = None
    title: Optional[str] = None
    role: Optional[str] = None

    promoted: bool = False
    media_object_id: Optional[str] = None

    raw: Dict[str, Any] = field(default_factory=dict)


# ==============================================================================
# Internal helpers
# ==============================================================================

def _iter_children(node: Any) -> List[Any]:
    return getattr(node, "children", []) or []


def _first_child_value(node: Any, tag: str) -> Optional[str]:
    for ch in _iter_children(node):
        if getattr(ch, "tag", None) == tag:
            return getattr(ch, "value", None)
    return None


def _find_inline_file_and_form(
    obje_node: Any,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Returns: (file_path, form, media_type)

    Supports:
      - FILE -> FORM -> TYPE / MEDI
    """
    file_path: Optional[str] = None
    form: Optional[str] = None
    media_type: Optional[str] = None

    for ch in _iter_children(obje_node):
        if getattr(ch, "tag", None) == "FILE":
            file_path = getattr(ch, "value", None)

            for fch in _iter_children(ch):
                if getattr(fch, "tag", None) == "FORM":
                    form = getattr(fch, "value", None)
                    for tf in _iter_children(fch):
                        if getattr(tf, "tag", None) in ("TYPE", "MEDI"):
                            media_type = getattr(tf, "value", None)
            break

    return file_path, form, media_type


# ==============================================================================
# Public extraction API (COMPATIBILITY SAFE)
# ==============================================================================

def extract_obje_attachments(
    owner_or_node: Any,
    node: Optional[Any] = None,
    *,
    origin: Optional[Dict[str, Any]] = None,
) -> List[AttachedRecord]:
    """
    Extract OBJE attachments from a GEDCOM record.

    Supported call forms:
      - extract_obje_attachments(node, origin={...})          # CURRENT canonical
      - extract_obje_attachments(owner, node, origin={...})   # FUTURE-compatible

    The function auto-detects which form is being used.
    """

    # ------------------------------------------------------------------
    # Normalize arguments
    # ------------------------------------------------------------------
    if node is None:
        # Called as extract_obje_attachments(node, origin=...)
        node = owner_or_node
        owner = None
    else:
        # Called as extract_obje_attachments(owner, node, origin=...)
        owner = owner_or_node

    if origin is None:
        origin = {}

    results: List[AttachedRecord] = []

    owner_pointer = origin.get("pointer")
    owner_type = origin.get("container")

    # ------------------------------------------------------------------
    # Extract OBJE children
    # ------------------------------------------------------------------
    for ch in _iter_children(node):
        if getattr(ch, "tag", None) != "OBJE":
            continue

        lineno = getattr(ch, "lineno", None)

        # Pointer-form OBJE
        ptr = getattr(ch, "pointer", None)
        if ptr:
            results.append(
                AttachedRecord(
                    pointer=ptr,
                    raw={
                        "kind": "pointer",
                        "owner_pointer": owner_pointer,
                        "owner_type": owner_type,
                        "lineno": lineno,
                        **origin,
                    },
                )
            )
            continue

        # Inline OBJE
        file_path, form, media_type = _find_inline_file_and_form(ch)
        title = _first_child_value(ch, "TITL")

        results.append(
            AttachedRecord(
                pointer=None,
                file=file_path,
                title=title,
                raw={
                    "kind": "inline",
                    "owner_pointer": owner_pointer,
                    "owner_type": owner_type,
                    "lineno": lineno,
                    "form": form,
                    "media_type": media_type,
                    **origin,
                },
            )
        )

    return results


def extract_attached_records(
    owner_or_node: Any,
    node: Optional[Any] = None,
    *,
    origin: Optional[Dict[str, Any]] = None,
) -> List[AttachedRecord]:
    """
    Generic wrapper for attachment extraction.
    """
    return extract_obje_attachments(owner_or_node, node, origin=origin)


# ==============================================================================
# Promotion helpers (unchanged behavior)
# ==============================================================================

def should_promote_inline_obje(obje_node: Any) -> bool:
    file_path, _, _ = _find_inline_file_and_form(obje_node)
    return bool(file_path)


def promote_inline_media_objects(registry: Any, tree: Any) -> int:
    """
    Phase 4.5 promotion pass (unchanged, idempotent).
    """
    from gedcom_parser.identity.uuid_factory import uuid_for_record
    from gedcom_parser.registry.entities import MediaFile, MediaObjectEntity

    created = 0
    obje_index: Dict[Tuple[Optional[str], Optional[int]], Any] = {}

    def index_objes(node: Any, container_pointer: Optional[str]) -> None:
        for ch in _iter_children(node):
            if getattr(ch, "tag", None) == "OBJE" and not getattr(ch, "pointer", None):
                key = (container_pointer, getattr(ch, "lineno", None))
                obje_index[key] = ch
            index_objes(ch, container_pointer)

    top_level = getattr(tree, "records", None) or getattr(tree, "children", []) or []

    for top in top_level:
        index_objes(top, getattr(top, "pointer", None))

    def node_to_record_dict(node: Any) -> Dict[str, Any]:
        return {
            "tag": getattr(node, "tag", None),
            "value": getattr(node, "value", None),
            "pointer": getattr(node, "pointer", None),
            "lineno": getattr(node, "lineno", None),
            "children": [node_to_record_dict(c) for c in _iter_children(node)],
        }

    def promote_on_entity(entity: Any) -> None:
        nonlocal created

        for att in getattr(entity, "attachments", []) or []:
            if att.pointer:
                att.media_object_id = att.pointer
                continue

            owner_ptr = att.raw.get("owner_pointer")
            lineno = att.raw.get("lineno")
            obje_node = obje_index.get((owner_ptr, lineno))
            if not obje_node or not should_promote_inline_obje(obje_node):
                continue

            record_dict = node_to_record_dict(obje_node)
            media_uuid = uuid_for_record(record_dict)

            if registry.get_media_object(media_uuid):
                att.media_object_id = media_uuid
                att.promoted = True
                continue

            file_path, form, media_type = _find_inline_file_and_form(obje_node)
            title = _first_child_value(obje_node, "TITL") or att.title

            media = MediaObjectEntity(
                uuid=media_uuid,
                pointer=None,
                title=title,
                files=[],
                raw={
                    "promoted_from": owner_ptr,
                    "lineno": lineno,
                    "source": "inline_OBJE",
                },
            )

            if file_path:
                media.files.append(
                    MediaFile(
                        path=file_path,
                        form=form,
                        media_type=media_type,
                        title=title,
                        raw={"source": "inline_OBJE"},
                    )
                )

            registry.register_media_object(media)
            created += 1

            att.media_object_id = media_uuid
            att.promoted = True

    for ind in registry.individuals.values():
        promote_on_entity(ind)
    for fam in registry.families.values():
        promote_on_entity(fam)
    for src in registry.sources.values():
        promote_on_entity(src)

    return created
