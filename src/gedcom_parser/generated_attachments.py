from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Protocol, Tuple
import re

from .entities import MediaObjectEntity, GedcomRegistry


# ==============================================================================
# Node protocol (matches loader.tree_builder node objects)
# ==============================================================================

class Node(Protocol):
    tag: str
    value: Optional[str]
    pointer: Optional[str]
    children: List["Node"]
    lineno: Optional[int]


# ==============================================================================
# Public models
# ==============================================================================

@dataclass
class AttachedRecord:
    """A single attachment occurrence on some entity (or nested event)."""

    media_xref: str
    primary: Optional[bool] = None

    # Path from the entity root to the node *containing* this OBJE link.
    # Example: ('BIRT',) means OBJE appeared under the BIRT structure.
    context: Tuple[str, ...] = field(default_factory=tuple)

    # True if this attachment came from inline OBJE promoted into a MediaObject record.
    promoted_from_inline: bool = False

    # Any unrecognized/extra vendor tags on the OBJE link (NOT the media object record).
    link_raw: Dict[str, Any] = field(default_factory=dict)


# ==============================================================================
# XREF factory (no collisions, preserves existing xrefs)
# ==============================================================================

_XREF_RE = re.compile(r"@[^@\s]+@")

class XrefFactory:
    def __init__(self, existing: Iterable[str], prefix: str = "O") -> None:
        self.prefix = prefix
        self.used = set(existing)
        self.counter = 1

    def reserve(self, xref: str) -> None:
        self.used.add(xref)

    def new(self) -> str:
        # Produces @O1@, @O2@, ... skipping any collisions.
        while True:
            xref = f"@{self.prefix}{self.counter}@"
            self.counter += 1
            if xref not in self.used:
                self.used.add(xref)
                return xref


def collect_xrefs_from_tree(root: Node) -> List[str]:
    """Collect existing xrefs from pointers AND values like '@S1@' anywhere."""
    found: set[str] = set()

    def walk(n: Node) -> None:
        if getattr(n, "pointer", None):
            found.add(n.pointer)  # type: ignore[arg-type]
        v = getattr(n, "value", None)
        if isinstance(v, str):
            for m in _XREF_RE.findall(v):
                found.add(m)
        for c in getattr(n, "children", []) or []:
            walk(c)

    walk(root)
    return sorted(found)


# ==============================================================================
# Parsing helpers
# ==============================================================================

def _child_values(node: Node, tag: str) -> List[str]:
    out: List[str] = []
    for c in node.children or []:
        if c.tag == tag and c.value is not None:
            out.append(c.value)
    return out

def _first_child_value(node: Node, tag: str) -> Optional[str]:
    vals = _child_values(node, tag)
    return vals[0] if vals else None

def _link_primary_from_obje(node: Node) -> Optional[bool]:
    # Common vendor forms:
    #   2 _PRIM Y
    #   2 _PRIM N
    v = _first_child_value(node, "_PRIM")
    if not v:
        return None
    v = v.strip().upper()
    if v in {"Y", "YES", "TRUE", "1"}:
        return True
    if v in {"N", "NO", "FALSE", "0"}:
        return False
    return None


def parse_media_object_record(obje_record_node: Node) -> MediaObjectEntity:
    """Parse a top-level OBJE record node into MediaObjectEntity."""
    pointer = obje_record_node.pointer or (obje_record_node.value or "")
    files: List[str] = []
    form: Optional[str] = None
    title: Optional[str] = None
    media_type: Optional[str] = None
    mime: Optional[str] = None
    notes: List[str] = []

    for c in obje_record_node.children or []:
        if c.tag == "FILE" and c.value:
            files.append(c.value)
            # FORM and TITL can appear under FILE
            form = form or _first_child_value(c, "FORM")
            title = title or _first_child_value(c, "TITL")
        elif c.tag == "FORM" and c.value:
            form = form or c.value
        elif c.tag == "TITL" and c.value:
            title = title or c.value
        elif c.tag in {"TYPE", "_TYPE"} and c.value:
            media_type = media_type or c.value
        elif c.tag in {"MIME", "_MIME"} and c.value:
            mime = mime or c.value
        elif c.tag == "NOTE" and c.value:
            notes.append(c.value)

    return MediaObjectEntity(
        pointer=pointer,
        files=files,
        form=form,
        title=title,
        media_type=media_type,
        mime=mime,
        notes=notes,
        raw={"lineno": getattr(obje_record_node, "lineno", None)},
    )


# ==============================================================================
# Promotion + extraction
# ==============================================================================

def _is_pointer_xref(value: Optional[str]) -> bool:
    return isinstance(value, str) and bool(_XREF_RE.fullmatch(value.strip()))

def _obje_is_inline(node: Node) -> bool:
    # Inline OBJE has no pointer-value xref but *does* have children like FILE.
    if _is_pointer_xref(node.value):
        return False
    for c in node.children or []:
        if c.tag in {"FILE", "FORM", "TITL"}:
            return True
    return False


def promote_inline_obje(
    obje_link_node: Node,
    registry: GedcomRegistry,
    xref_factory: XrefFactory,
    debug: bool = False,
    debug_sink: Optional[List[str]] = None,
) -> str:
    """Promote inline OBJE to a top-level MediaObjectEntity, return new media xref."""

    # Build a synthetic OBJE record node view using the inline node's children.
    # We treat FILE/FORM/TITL/TYPE/MIME/NOTE as record-level; _PRIM stays link-level.
    record_like_children: List[Node] = []
    link_children: List[Node] = []

    for c in obje_link_node.children or []:
        if c.tag in {"_PRIM"}:
            link_children.append(c)
        else:
            record_like_children.append(c)

    new_xref = xref_factory.new()
    media_entity = _parse_inline_media(new_xref, record_like_children, lineno=getattr(obje_link_node, "lineno", None))
    registry.register_media_object(media_entity)

    # Mutate the existing inline link node into a pointer link.
    obje_link_node.value = new_xref
    obje_link_node.children = link_children

    msg = f"PROMOTE inline OBJE at line {getattr(obje_link_node, 'lineno', None)} -> {new_xref}"
    if debug:
        if debug_sink is not None:
            debug_sink.append(msg)
        else:
            print(msg)

    return new_xref


def _parse_inline_media(new_xref: str, children: List[Node], lineno: Optional[int]) -> MediaObjectEntity:
    # Similar to parse_media_object_record, but we only have the child list.
    files: List[str] = []
    form: Optional[str] = None
    title: Optional[str] = None
    media_type: Optional[str] = None
    mime: Optional[str] = None
    notes: List[str] = []

    for c in children or []:
        if c.tag == "FILE" and c.value:
            files.append(c.value)
            form = form or _first_child_value(c, "FORM")
            title = title or _first_child_value(c, "TITL")
        elif c.tag == "FORM" and c.value:
            form = form or c.value
        elif c.tag == "TITL" and c.value:
            title = title or c.value
        elif c.tag in {"TYPE", "_TYPE"} and c.value:
            media_type = media_type or c.value
        elif c.tag in {"MIME", "_MIME"} and c.value:
            mime = mime or c.value
        elif c.tag == "NOTE" and c.value:
            notes.append(c.value)

    return MediaObjectEntity(
        pointer=new_xref,
        files=files,
        form=form,
        title=title,
        media_type=media_type,
        mime=mime,
        notes=notes,
        raw={"promoted_from_inline": True, "lineno": lineno},
    )


def extract_attachments(
    entity_root: Node,
    registry: GedcomRegistry,
    xref_factory: XrefFactory,
    *,
    debug: bool = False,
    debug_sink: Optional[List[str]] = None,
) -> List[AttachedRecord]:
    """Extract all OBJE links under an entity, promoting inline OBJE where needed.

    Returns a flat list of AttachedRecord, preserving the nested context path.
    """
    attachments: List[AttachedRecord] = []

    def walk(n: Node, path: Tuple[str, ...]) -> None:
        # We don't include the OBJE tag itself in the context; instead we attach it to its parent path.
        if n.tag == "OBJE":
            promoted = False
            if _obje_is_inline(n):
                media_xref = promote_inline_obje(n, registry, xref_factory, debug=debug, debug_sink=debug_sink)
                promoted = True
            else:
                media_xref = (n.value or "").strip()

            if media_xref:
                attachments.append(
                    AttachedRecord(
                        media_xref=media_xref,
                        primary=_link_primary_from_obje(n),
                        context=path,
                        promoted_from_inline=promoted,
                        link_raw={c.tag: c.value for c in (n.children or []) if c.tag != "_PRIM"},
                    )
                )
            return

        for c in n.children or []:
            # Context path rules:
            # - At the entity root, we don't include INDI/FAM/SOUR itself.
            # - For nested structures, we include their tag (e.g., BIRT, EVEN).
            next_path = path
            if n is not entity_root:
                next_path = path + (n.tag,)
            walk(c, next_path)

    walk(entity_root, tuple())
    return attachments
