# src/gedcom_parser/attachments.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple


# ------------------------------------------------------------
# AttachedRecord
# ------------------------------------------------------------

@dataclass
class AttachedRecord:
    """
    Normalized attachment reference on an entity.

    Represents:
      - pointer OBJE reference (@O123@)
      - inline OBJE (no pointer, has FILE/TITL/etc)
      - promoted inline OBJE (inline content promoted to a MediaObjectEntity)

    Step 4.5 promotion MUST be:
      - re-runnable
      - idempotent
      - safe if some references are missing
    """
    media_object_id: Optional[str] = None   # uuid (promoted) OR pointer (pointer-form)
    pointer: Optional[str] = None           # GEDCOM pointer like "@O123@"
    file: Optional[str] = None
    title: Optional[str] = None
    form: Optional[str] = None
    media_type: Optional[str] = None
    role: Optional[str] = None
    promoted: bool = False
    raw: Dict[str, Any] = field(default_factory=dict)


# ------------------------------------------------------------
# Node helpers
# ------------------------------------------------------------

def _norm_tag(tag: Optional[str]) -> str:
    return (tag or "").strip().upper()


def _iter_children(node: Any) -> Iterable[Any]:
    return getattr(node, "children", []) or []


def _child_value(node: Any, tag: str) -> Optional[str]:
    want = _norm_tag(tag)
    for ch in _iter_children(node):
        if _norm_tag(getattr(ch, "tag", None)) == want:
            val = getattr(ch, "value", None)
            if val is not None:
                return val
    return None


def _child_node(node: Any, tag: str) -> Optional[Any]:
    want = _norm_tag(tag)
    for ch in _iter_children(node):
        if _norm_tag(getattr(ch, "tag", None)) == want:
            return ch
    return None


def _collect_file_entries(obje_node: Any) -> List[Dict[str, Optional[str]]]:
    """
    Collect FILE blocks under OBJE.

    Variants:
      OBJE
        FILE path
          FORM jpg
          TITL caption
          TYPE photo
    """
    out: List[Dict[str, Optional[str]]] = []
    for ch in _iter_children(obje_node):
        if _norm_tag(getattr(ch, "tag", None)) != "FILE":
            continue

        path = getattr(ch, "value", None)
        form = _child_value(ch, "FORM")
        titl = _child_value(ch, "TITL")
        typ = _child_value(ch, "TYPE")

        out.append({"path": path, "form": form, "title": titl, "media_type": typ})
    return out


# ------------------------------------------------------------
# Promotion heuristic
# ------------------------------------------------------------

def should_promote_inline_obje(obje_node: Any) -> bool:
    """
    Best-practice heuristic:
    Promote inline OBJE if it provides meaningful content:
      - FILE path (strong signal)
      - or TITL (weak signal, but still meaningful)
    """
    if obje_node is None:
        return False

    if _child_node(obje_node, "FILE") is not None:
        return True

    titl = _child_value(obje_node, "TITL")
    return bool(titl and titl.strip())


# ------------------------------------------------------------
# Extraction (builders call this)
# ------------------------------------------------------------

def parse_obje_node(obje_node: Any, *, origin: Dict[str, Any]) -> AttachedRecord:
    rec = AttachedRecord(raw=dict(origin))
    rec.raw["lineno"] = getattr(obje_node, "lineno", None)

    ptr = getattr(obje_node, "pointer", None)
    if ptr:
        rec.pointer = ptr
        rec.media_object_id = ptr  # safe default for pointer-form
        return rec

    # Inline OBJE
    titl = _child_value(obje_node, "TITL")
    if titl:
        rec.title = titl

    file_entries = _collect_file_entries(obje_node)
    if file_entries and file_entries[0].get("path"):
        rec.file = file_entries[0].get("path")
        rec.form = file_entries[0].get("form")
        rec.media_type = file_entries[0].get("media_type")
        # Prefer FILE.TITL over OBJE.TITL if present
        if file_entries[0].get("title"):
            rec.title = file_entries[0].get("title") or rec.title

    # Custom role tags: first "_" tag under OBJE
    for ch in _iter_children(obje_node):
        t = getattr(ch, "tag", None)
        if isinstance(t, str) and t.startswith("_"):
            rec.role = t
            break

    return rec


def extract_attached_records(owner_entity: Any, node: Any) -> List[AttachedRecord]:
    """
    Extract direct-child OBJE nodes into AttachedRecord objects.
    No promotion here (promotion is Phase 4.5).
    """
    origin = {
        "owner_pointer": getattr(owner_entity, "pointer", None),
        "owner_uuid": getattr(owner_entity, "uuid", None),
        "owner_type": type(owner_entity).__name__,
    }

    out: List[AttachedRecord] = []
    for ch in _iter_children(node):
        if _norm_tag(getattr(ch, "tag", None)) == "OBJE":
            out.append(parse_obje_node(ch, origin=origin))
    return out

# ------------------------------------------------------------------
# Backwards-compatibility shim (builders depend on this name)
# ------------------------------------------------------------------

def extract_obje_attachments(node: Any, *, origin: Optional[Dict[str, Any]] = None):
    """
    Compatibility wrapper for legacy builder imports.

    Adapts:
        extract_obje_attachments(node, origin=...)

    To:
        extract_attached_records(owner_entity=None, node)

    NOTE:
      - owner_entity is unknown at this stage
      - origin metadata is preserved in AttachedRecord.raw
    """
    origin = dict(origin or {})

    attachments = []
    for ch in getattr(node, "children", []) or []:
        if _norm_tag(getattr(ch, "tag", None)) == "OBJE":
            rec = parse_obje_node(ch, origin=origin)
            attachments.append(rec)

    return attachments

# ------------------------------------------------------------
# Phase 4.5: promotion pass (run after linking)
# ------------------------------------------------------------

def _node_to_record_dict(node: Any) -> Dict[str, Any]:
    return {
        "tag": getattr(node, "tag", None),
        "value": getattr(node, "value", None),
        "pointer": getattr(node, "pointer", None),
        "lineno": getattr(node, "lineno", None),
        "children": [_node_to_record_dict(c) for c in _iter_children(node)],
    }


def promote_inline_media_objects(registry: Any, tree: Any) -> int:
    """
    Phase 4.5 promotion:
      - index inline OBJE nodes from GEDCOMTree.records
      - for each entity attachment:
          - pointer-form: ensure media_object_id set to pointer
          - inline-form: promote if qualifies, idempotently

    Returns:
      number of newly-created promoted media objects
    """
    # Local imports to avoid circular imports
    from gedcom_parser.identity.uuid_factory import uuid_for_record
    from gedcom_parser.registry.entities import MediaFile, MediaObjectEntity

    created = 0

    # Index inline OBJE nodes by (top_record_pointer, lineno)
    obje_index: Dict[Tuple[Optional[str], Optional[int]], Any] = {}

    def index_inline_objes(node: Any, top_ptr: Optional[str]) -> None:
        for ch in _iter_children(node):
            if _norm_tag(getattr(ch, "tag", None)) == "OBJE" and not getattr(ch, "pointer", None):
                key = (top_ptr, getattr(ch, "lineno", None))
                obje_index[key] = ch
            index_inline_objes(ch, top_ptr)

    for top in getattr(tree, "records", []) or []:
        top_ptr = getattr(top, "pointer", None)
        index_inline_objes(top, top_ptr)

    def promote_entity(entity: Any) -> None:
        nonlocal created

        for att in getattr(entity, "attachments", []) or []:
            # Pointer-form is already a stable reference.
            if att.pointer:
                att.media_object_id = att.pointer
                continue

            # Already promoted and present -> idempotent no-op
            if att.promoted and att.media_object_id and att.media_object_id in getattr(registry, "media_objects", {}):
                continue

            owner_ptr = att.raw.get("owner_pointer")
            lineno = att.raw.get("lineno")
            obje_node = obje_index.get((owner_ptr, lineno))

            if not obje_node:
                continue
            if not should_promote_inline_obje(obje_node):
                continue

            record_dict = _node_to_record_dict(obje_node)
            media_uuid = uuid_for_record(record_dict)

            # If already created earlier in the run, link it (idempotent)
            if media_uuid in getattr(registry, "media_objects", {}):
                att.media_object_id = media_uuid
                att.promoted = True
                continue

            media = MediaObjectEntity(
                uuid=media_uuid,
                pointer=None,
                title=att.title,
                files=[],
                raw={
                    "promoted_from": "inline_OBJE",
                    "owner_pointer": owner_ptr,
                    "owner_type": att.raw.get("owner_type"),
                    "lineno": lineno,
                },
            )

            if att.file:
                media.files.append(
                    MediaFile(
                        path=att.file,
                        form=att.form,
                        media_type=att.media_type,
                        title=att.title,
                        raw={"role": att.role, "source": "inline_OBJE"},
                    )
                )

            registry.register_media_object(media)

            att.media_object_id = media_uuid
            att.promoted = True
            created += 1

    for ind in getattr(registry, "individuals", {}).values():
        promote_entity(ind)
    for fam in getattr(registry, "families", {}).values():
        promote_entity(fam)
    for src in getattr(registry, "sources", {}).values():
        promote_entity(src)

    return created
