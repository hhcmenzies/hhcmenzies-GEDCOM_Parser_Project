from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class IndividualEntity:
    pointer: str
    root: Dict[str, Any]
    facts: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FamilyEntity:
    pointer: str
    root: Dict[str, Any]
    members: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SourceEntity:
    pointer: str
    root: Dict[str, Any]
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RepositoryEntity:
    pointer: str
    root: Dict[str, Any]
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MediaObjectEntity:
    pointer: str
    root: Dict[str, Any]
    meta: Dict[str, Any] = field(default_factory=dict)
