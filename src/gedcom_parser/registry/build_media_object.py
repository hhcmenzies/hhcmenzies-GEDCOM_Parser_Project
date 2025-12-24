from __future__ import annotations

from gedcom_parser.identity.uuid_factory import uuid_for_pointer
from gedcom_parser.registry.entities import MediaObjectEntity, MediaFile, GenericAttribute

def build_media_object(node) -> MediaObjectEntity:
    """
    Build a MediaObjectEntity from a GEDCOM node with tag 'OBJE' (top-level multimedia record).

    PURE FUNCTION:
      - no cross-entity linking (only collects pointers to notes/sources)
      - no side effects on registry
      - fully captures all substructure of the OBJE record (files, format, title, notes, sources, custom tags).
    """
    if getattr(node, "tag", None) != "OBJE":
        raise ValueError(f"Expected OBJE node, got {getattr(node, 'tag', None)}")
    pointer = getattr(node, "pointer", None)
    # It's possible for a top-level OBJE to be missing a pointer (not typical). 
    # We require pointer for registry indexing.
    if not pointer:
        raise ValueError("OBJE node is missing pointer")

    media = MediaObjectEntity(
        uuid=uuid_for_pointer(pointer),
        pointer=pointer,
    )

    # Gather file(s)
    files: List[MediaFile] = []
    for child in getattr(node, "children", []) or []:
        if child.tag == "FILE":
            # Each FILE structure (GEDCOM 5.5 or 5.5.1)
            file_path = child.value or ""
            file_format = None
            file_media_type = None
            file_raw: Dict[str, Any] = {}
            # GEDCOM 5.5.1: FORM is a substructure of FILE
            form_node = None
            if child.children:
                # If there are sub-children, likely a FORM structure is present
                form_node = next((c for c in child.children if c.tag == "FORM"), None)
            if form_node:
                file_format = form_node.value
                # Under FORM, there might be TYPE (media type) or other custom tags
                for fch in form_node.children or []:
                    if fch.tag in ("TYPE", "MEDI"):
                        file_media_type = fch.value
                    else:
                        # e.g. _STYPE, _SIZE, _WDTH, _HGHT or other custom tags under FORM
                        file_raw[fch.tag] = fch.value
            else:
                # GEDCOM 5.5: FORM might be a sibling of FILE
                # Try to find a FORM sibling if not already found
                form_node = next((s for s in node.children or [] if s.tag == "FORM"), None)
                if form_node:
                    file_format = form_node.value
                # Also look for a media type sibling (MEDI/TYPE) if present
                type_node = next((s for s in node.children or [] if s.tag in ("TYPE", "MEDI")), None)
                if type_node:
                    file_media_type = type_node.value
            # Create MediaFile for this file entry
            media_file = MediaFile(
                path=file_path,
                form=file_format,
                media_type=file_media_type,
                title=None,  # No separate title per file; title is at media record level
                raw=file_raw if file_raw else {}
            )
            files.append(media_file)
    if files:
        media.files.extend(files)

    # Title
    title_node = next((c for c in getattr(node, "children", []) or [] if c.tag == "TITL"), None)
    if title_node:
        media.title = title_node.value

    # Notes
    for child in getattr(node, "children", []) or []:
        if child.tag == "NOTE":
            if child.pointer:
                media.note_pointers.append(child.pointer)
            elif child.value:
                media.note_texts.append(child.value)

    # Sources
    for child in getattr(node, "children", []) or []:
        if child.tag == "SOUR" and child.pointer:
            media.source_pointers.append(child.pointer)

    # Attributes (capture any other tags like REFN, RIN, _CREA, _OID, _DSCR, etc.)
    for child in getattr(node, "children", []) or []:
        tag = child.tag
        if tag in {"FILE", "FORM", "TYPE", "MEDI", "TITL", "NOTE", "SOUR"}:
            # Already handled above
            continue
        media.attributes.append(
            GenericAttribute(
                tag=tag,
                value=child.value,
                pointer=child.pointer,
                children=[
                    {"tag": gc.tag, "value": gc.value, "pointer": gc.pointer}
                    for gc in (child.children or [])
                ],
                lineno=getattr(child, "lineno", None),
            )
        )

    return media
