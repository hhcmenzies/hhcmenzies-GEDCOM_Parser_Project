from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    # Avoid runtime circular imports:
    # attachments.py may import registry entities (only inside functions), and
    # entities.py must NOT import attachments at import-time.
    from gedcom_parser.attachments import AttachedRecord


# -----------------------------
# Core “record” building blocks
# -----------------------------

@dataclass(slots=True)
class NameRecord:
    """
    Normalized container for an individual's name block.

    This is intentionally minimal and stable; enrichment can extend via `raw`.
    """
    raw: str
    given: Optional[str] = None
    surname: Optional[str] = None
    prefix: Optional[str] = None
    suffix: Optional[str] = None
    nickname: Optional[str] = None
    raw_parts: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AttributeRecord:
    """
    Generic, lossless attribute capture (tag/value/pointer/children).
    Used when we don’t yet model a GEDCOM tag as a first-class field.
    """
    tag: str
    value: Optional[str] = None
    pointer: Optional[str] = None
    children: List[Dict[str, Any]] = field(default_factory=list)
    lineno: Optional[int] = None


# Keep existing naming used across builders/tests
GenericAttribute = AttributeRecord


# -----------------------------
# Media entities
# -----------------------------

@dataclass(slots=True)
class MediaFile:
    path: str
    title: Optional[str] = None
    mime: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MediaObjectEntity:
    uuid: str
    pointer: Optional[str] = None  # @M123@ for top-level OBJE; None for promoted inline OBJE
    title: Optional[str] = None
    files: List[MediaFile] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)


# -----------------------------
# Source / Note entities
# -----------------------------

@dataclass(slots=True)
class SourceEntity:
    uuid: str
    pointer: str
    title: Optional[str] = None
    text: Optional[str] = None
    notes: List[str] = field(default_factory=list)
    media: List[str] = field(default_factory=list)  # OBJE pointers or promoted UUIDs (post-promotion)
    attributes: List[AttributeRecord] = field(default_factory=list)
    attachments: List["AttachedRecord"] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class NoteEntity:
    uuid: str
    pointer: str
    text: str
    raw: Dict[str, Any] = field(default_factory=dict)


# -----------------------------
# Family / Individual entities
# -----------------------------

@dataclass(slots=True)
class FamilyEntity:
    uuid: str
    pointer: str

    husband: Optional[str] = None  # @I1@
    wife: Optional[str] = None     # @I2@
    children: List[str] = field(default_factory=list)

    events: List[Dict[str, Any]] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)

    attributes: List[AttributeRecord] = field(default_factory=list)
    attachments: List["AttachedRecord"] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class IndividualEntity:
    uuid: str
    pointer: str

    sex: Optional[str] = None

    # Name blocks (Phase 4.3+)
    names: List[NameRecord] = field(default_factory=list)

    # Event extraction outputs (already used by your tests)
    events: List[Dict[str, Any]] = field(default_factory=list)

    # Generic attributes (lossless capture)
    attributes: List[AttributeRecord] = field(default_factory=list)

    # Attachments extracted from OBJE (Phase 4.5 promotion runs later)
    attachments: List["AttachedRecord"] = field(default_factory=list)

    # -------------------------
    # Relationship linking fields
    # (link_entities() expects these EXACT names)
    # -------------------------
    spouse_in_families: List[str] = field(default_factory=list)  # list of family pointers (@F1@)
    child_in_families: List[str] = field(default_factory=list)   # list of family pointers (@F1@)

    # Keep older semantic aliases, but as computed properties (no duplication).
    @property
    def families_as_spouse(self) -> List[str]:
        return self.spouse_in_families

    @property
    def families_as_child(self) -> List[str]:
        return self.child_in_families

    raw: Dict[str, Any] = field(default_factory=dict)


# -----------------------------
# Registry container
# -----------------------------

@dataclass(slots=True)
class GedcomRegistry:
    individuals: Dict[str, IndividualEntity] = field(default_factory=dict)
    families: Dict[str, FamilyEntity] = field(default_factory=dict)
    sources: Dict[str, SourceEntity] = field(default_factory=dict)
    notes: Dict[str, NoteEntity] = field(default_factory=dict)
    media_objects: Dict[str, MediaObjectEntity] = field(default_factory=dict)

    # ---- register ----
    def register_individual(self, ind: IndividualEntity) -> None:
        self.individuals[ind.pointer] = ind

    def register_family(self, fam: FamilyEntity) -> None:
        self.families[fam.pointer] = fam

    def register_source(self, src: SourceEntity) -> None:
        self.sources[src.pointer] = src

    def register_note(self, note: NoteEntity) -> None:
        self.notes[note.pointer] = note

    def register_media_object(self, media: MediaObjectEntity) -> None:
        # pointer may be None for promoted inline objects; store by uuid in that case
        key = media.pointer or media.uuid
        self.media_objects[key] = media

    # ---- get ----
    def get_individual(self, pointer: str) -> Optional[IndividualEntity]:
        return self.individuals.get(pointer)

    def get_family(self, pointer: str) -> Optional[FamilyEntity]:
        return self.families.get(pointer)

    def get_source(self, pointer: str) -> Optional[SourceEntity]:
        return self.sources.get(pointer)

    def get_note(self, pointer: str) -> Optional[NoteEntity]:
        return self.notes.get(pointer)

    def get_media_object(self, key: str) -> Optional[MediaObjectEntity]:
        return self.media_objects.get(key)
