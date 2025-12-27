from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING


# -----------------------------
# Base records (small atoms)
# -----------------------------

@dataclass(slots=True)
class NameRecord:
    """
    GEDCOM NAME substructure.

    Tests/builders expect:
      - NameRecord(full="John /Doe/")
      - optional components (given/surname/prefix/suffix/nickname/name_type)
    """
    full: str = ""
    given: Optional[str] = None
    surname: Optional[str] = None
    prefix: Optional[str] = None
    suffix: Optional[str] = None
    nickname: Optional[str] = None
    name_type: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EventRecord:
    """
    Generic event container used by event extraction.

    Keep permissive: different GEDCOM producers emit different shapes.
    """
    tag: str
    date: Optional[str] = None
    place: Optional[str] = None
    value: Optional[str] = None
    role: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class GenericAttribute:
    """
    Lossless capture of unmodeled GEDCOM tags/attributes.

    Supports:
      - nested substructures (children)
      - source line tracking (lineno)
      - vendor / future GEDCOM extensions
    """
    tag: str
    value: Optional[str] = None
    pointer: Optional[str] = None

    # Nested tag/value structures preserved verbatim
    children: List[Dict[str, Any]] = field(default_factory=list)

    # Original GEDCOM line number (if available)
    lineno: Optional[int] = None

    # Any additional metadata not explicitly modeled
    raw: Dict[str, Any] = field(default_factory=dict)

# Backward-compatible internal alias (REQUIRED)
AttributeRecord = GenericAttribute

# -----------------------------
# Media
# -----------------------------

@dataclass(slots=True)
class MediaFile:
    """
    Tests/builders expect:
      MediaFile(path=..., form=..., media_type=...)
    """
    path: str
    form: Optional[str] = None
    media_type: Optional[str] = None
    title: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)


# -----------------------------
# Entities
# -----------------------------

if TYPE_CHECKING:
    # Avoid runtime cycles: attachments imports nothing from registry.entities
    from gedcom_parser.attachments import AttachedRecord


@dataclass(slots=True)
class IndividualEntity:
    uuid: str
    pointer: str

    # Modeled
    gender: Optional[str] = None
    names: List[NameRecord] = field(default_factory=list)
    events: List[EventRecord] = field(default_factory=list)
    occupations: List[str] = field(default_factory=list)

    # Pointers captured during build (pre-link)
    families_as_spouse: List[str] = field(default_factory=list)  # FAMS
    families_as_child: List[str] = field(default_factory=list)   # FAMC

    # Cross-entity resolved fields (Phase 4.3 linking pass)
    spouse_in_families: List["FamilyEntity"] = field(default_factory=list)
    child_in_families: List["FamilyEntity"] = field(default_factory=list)

    # Common GEDCOM cross refs / misc
    notes: List[str] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    attributes: List[GenericAttribute] = field(default_factory=list)
    attachments: List["AttachedRecord"] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class FamilyEntity:
    uuid: str
    pointer: str

    # Pointers captured during build (pre-link)
    husband: Optional[str] = None
    wife: Optional[str] = None
    children: List[str] = field(default_factory=list)

    # Modeled
    events: List[EventRecord] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    attributes: List[GenericAttribute] = field(default_factory=list)
    attachments: List["AttachedRecord"] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)

    # Cross-entity resolved fields (Phase 4.3 linking pass)
    husband_entity: Optional[IndividualEntity] = None
    wife_entity: Optional[IndividualEntity] = None
    children_entities: List[IndividualEntity] = field(default_factory=list)


@dataclass(slots=True)
class SourceEntity:
    uuid: str
    pointer: str

    title: Optional[str] = None
    author: Optional[str] = None
    publication: Optional[str] = None
    repository_pointer: Optional[str] = None

    notes: List[str] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    attributes: List[GenericAttribute] = field(default_factory=list)
    attachments: List["AttachedRecord"] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class NoteEntity:
    uuid: str
    pointer: str
    text: str = ""

    # Tests/builders expect NoteEntity(attributes=[...])
    attributes: List[GenericAttribute] = field(default_factory=list)

    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MediaObjectEntity:
    uuid: str
    pointer: Optional[str] = None

    title: Optional[str] = None
    files: List[MediaFile] = field(default_factory=list)
    attributes: List[GenericAttribute] = field(default_factory=list)

    # Optional cross refs (keep generic)
    notes: List[str] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)

    raw: Dict[str, Any] = field(default_factory=dict)


# -----------------------------
# Registry
# -----------------------------

@dataclass(slots=True)
class GedcomRegistry:
    """
    In-memory entity store indexed by GEDCOM pointer where available.
    """
    individuals: Dict[str, IndividualEntity] = field(default_factory=dict)
    families: Dict[str, FamilyEntity] = field(default_factory=dict)
    sources: Dict[str, SourceEntity] = field(default_factory=dict)
    notes: Dict[str, NoteEntity] = field(default_factory=dict)
    media_objects: Dict[str, MediaObjectEntity] = field(default_factory=dict)

    def register_individual(self, ind: IndividualEntity) -> None:
        self.individuals[ind.pointer] = ind

    def register_family(self, fam: FamilyEntity) -> None:
        self.families[fam.pointer] = fam

    def register_source(self, src: SourceEntity) -> None:
        self.sources[src.pointer] = src

    def register_note(self, note: NoteEntity) -> None:
        self.notes[note.pointer] = note

    def register_media_object(self, media: MediaObjectEntity) -> None:
        # Media can be pointer-based or UUID-based (promoted inline).
        key = media.pointer or media.uuid
        self.media_objects[key] = media

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
