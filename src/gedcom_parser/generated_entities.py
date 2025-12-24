from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ==============================================================================
# Core entity models
# ==============================================================================

@dataclass
class NameRecord:
    """Represents an INDI NAME structure."""

    full: str
    givn: Optional[str] = None
    surn: Optional[str] = None
    nick: Optional[str] = None
    npfx: Optional[str] = None
    nsfx: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CitationRecord:
    """Represents a SOURCE_CITATION (SOUR pointer with optional PAGE/DATA/etc)."""

    source_xref: str
    page: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    quality: Optional[int] = None
    text: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EventRecord:
    """Generic event/attribute container (BIRT, DEAT, EVEN, OCCU, RESI, etc.)."""

    tag: str
    value: Optional[str] = None
    type: Optional[str] = None
    date: Optional[str] = None
    place: Optional[str] = None
    notes: List[str] = field(default_factory=list)
    sources: List[CitationRecord] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)


# NOTE: AttachedRecord is defined in src/gedcom_parser/attachments.py.
# We use a forward reference here to avoid import cycles.
AttachedRecord = Any  # type: ignore


@dataclass
class IndividualEntity:
    pointer: str
    names: List[NameRecord] = field(default_factory=list)
    sex: Optional[str] = None

    famc: List[str] = field(default_factory=list)   # family-as-child pointers
    fams: List[str] = field(default_factory=list)   # family-as-spouse pointers

    events: List[EventRecord] = field(default_factory=list)

    notes: List[str] = field(default_factory=list)  # plain text notes (already de-concatenated)
    sources: List[CitationRecord] = field(default_factory=list)

    attachments: List[AttachedRecord] = field(default_factory=list)

    attributes: Dict[str, Any] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FamilyEntity:
    pointer: str
    husb: Optional[str] = None
    wife: Optional[str] = None
    chil: List[str] = field(default_factory=list)

    events: List[EventRecord] = field(default_factory=list)

    notes: List[str] = field(default_factory=list)
    sources: List[CitationRecord] = field(default_factory=list)

    attachments: List[AttachedRecord] = field(default_factory=list)

    attributes: Dict[str, Any] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SourceEntity:
    pointer: str
    title: Optional[str] = None
    author: Optional[str] = None
    publication: Optional[str] = None
    repository: Optional[str] = None
    notes: List[str] = field(default_factory=list)

    attachments: List[AttachedRecord] = field(default_factory=list)

    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NoteEntity:
    pointer: str
    text: str
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MediaObjectEntity:
    """Represents a top-level OBJE record (multimedia object)."""

    pointer: str
    files: List[str] = field(default_factory=list)   # may contain 1+ FILE entries across vendors
    form: Optional[str] = None                       # e.g., jpg, png
    title: Optional[str] = None                      # TITL
    media_type: Optional[str] = None                 # _TYPE or TYPE (vendor-specific)
    mime: Optional[str] = None                       # _MIME or MIME (vendor-specific)
    notes: List[str] = field(default_factory=list)

    raw: Dict[str, Any] = field(default_factory=dict)


# ==============================================================================
# Registry
# ==============================================================================

@dataclass
class GedcomRegistry:
    individuals: Dict[str, IndividualEntity] = field(default_factory=dict)
    families: Dict[str, FamilyEntity] = field(default_factory=dict)
    sources: Dict[str, SourceEntity] = field(default_factory=dict)
    notes: Dict[str, NoteEntity] = field(default_factory=dict)
    media_objects: Dict[str, MediaObjectEntity] = field(default_factory=dict)

    # ---- Lookups ----------------------------------------------------------------

    def get_individual(self, pointer: str) -> Optional[IndividualEntity]:
        return self.individuals.get(pointer)

    def get_family(self, pointer: str) -> Optional[FamilyEntity]:
        return self.families.get(pointer)

    def get_source(self, pointer: str) -> Optional[SourceEntity]:
        return self.sources.get(pointer)

    def get_note(self, pointer: str) -> Optional[NoteEntity]:
        return self.notes.get(pointer)

    def get_media_object(self, pointer: str) -> Optional[MediaObjectEntity]:
        return self.media_objects.get(pointer)

    # ---- Registration helpers ----------------------------------------------------

    def register_individual(self, entity: IndividualEntity) -> None:
        self.individuals[entity.pointer] = entity

    def register_family(self, entity: FamilyEntity) -> None:
        self.families[entity.pointer] = entity

    def register_source(self, entity: SourceEntity) -> None:
        self.sources[entity.pointer] = entity

    def register_note(self, entity: NoteEntity) -> None:
        self.notes[entity.pointer] = entity

    def register_media_object(self, entity: MediaObjectEntity) -> None:
        self.media_objects[entity.pointer] = entity
