from collections.abc import MutableMapping
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator


@dataclass
class IndividualEntity(MutableMapping):
    pointer: str
    root: Dict[str, Any]
    facts: Dict[str, Any] = field(default_factory=dict)

    # MutableMapping interface delegates to facts
    def __getitem__(self, key: str) -> Any:
        return self.facts[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.facts[key] = value

    def __delitem__(self, key: str) -> None:
        del self.facts[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.facts)

    def __len__(self) -> int:
        return len(self.facts)

    def as_dict(self) -> Dict[str, Any]:
        return self.facts


@dataclass
class FamilyEntity:
    pointer: str
    root: Dict[str, Any]
    members: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return self.members


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
