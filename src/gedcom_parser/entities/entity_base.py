"""
entity_base.py

Common base class for genealogical entities (Individual, Family, Source, etc.).

Goals:
- Provide a shared set of core fields (pointer, tag, uuid, notes, sources, extras).
- Provide a safe, cycle-aware serialization method (`to_dict`) suitable for JSON export.
- Play nicely with:
    * dataclasses
    * Pydantic models (e.g. NameBlock / NormalizedName)
    * simple nested dict/list structures

This module is intentionally lightweight and does NOT depend on the rest of the
entities package, so it can be imported early by registry, models, exporter, etc.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any, Dict, List, Optional, Set
from uuid import UUID, uuid4

try:
    # Optional: for Pydantic-based sub-objects like NameBlock
    from pydantic import BaseModel as PydanticBaseModel  # type: ignore
except Exception:  # pragma: no cover - pydantic may not be installed in all contexts
    class PydanticBaseModel:  # type: ignore[no-redef]
        """Fallback shim if Pydantic is not installed in all contexts."""
        pass

from gedcom_parser.logger import get_logger

log = get_logger("entities.entity_base")


@dataclass
class BaseEntity:
    """
    Base class for all entity types stored in the EntityRegistry.

    Fields
    ------
    pointer:
        Original GEDCOM pointer (e.g. '@I123@', '@F45@', '@S12@').
    tag:
        Record type tag (e.g. 'INDI', 'FAM', 'SOUR', 'REPO', 'OBJE').
    uuid:
        Stable UUID for this entity instance. By default, a random v4 UUID is
        generated, but callers can override this if they need deterministic IDs.
    payload:
        Main structured data payload for this entity. This typically includes
        parsed fields such as name_block, events, attributes, etc.
    notes:
        Any notes associated with the entity (inline or record-level).
    sources:
        Source/citation identifiers associated with this entity.
    extras:
        Catch-all for tags/fields we don't yet model explicitly. This ensures we
        never silently drop information from the GEDCOM: “nothing should be excluded”.
    """

    pointer: str
    tag: str

    uuid: UUID = field(default_factory=uuid4)
    payload: Dict[str, Any] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    extras: Dict[str, Any] = field(default_factory=dict)

    # -------------------------------------------------------------------------
    # Convenience properties
    # -------------------------------------------------------------------------
    @property
    def id(self) -> str:
        """Alias for the GEDCOM pointer, for compatibility with older code."""
        return self.pointer

    # -------------------------------------------------------------------------
    # Serialization
    # -------------------------------------------------------------------------
    def to_dict(
        self,
        *,
        include_uuid: bool = True,
        include_pointer: bool = True,
        include_tag: bool = True,
    ) -> Dict[str, Any]:
        """
        Convert this entity into a JSON-serializable dictionary.

        This method is careful to:
        - Serialize nested BaseEntity instances by pointer to avoid cycles.
        - Serialize dataclasses via dataclasses.asdict.
        - Serialize Pydantic models via .model_dump().
        - Recursively handle lists/dicts.

        Parameters
        ----------
        include_uuid:
            If True, include "uuid" in the output.
        include_pointer:
            If True, include "id" (GEDCOM pointer) in the output.
        include_tag:
            If True, include "tag" in the output.

        Returns
        -------
        dict
            A JSON-ready dictionary representing this entity.
        """

        # use `id()` to avoid infinite recursion
        seen: Set[int] = set()
        data: Dict[str, Any] = {}

        if include_pointer:
            data["id"] = self.pointer
        if include_uuid:
            data["uuid"] = str(self.uuid)
        if include_tag:
            data["tag"] = self.tag

        data["payload"] = self._serialize_value(self.payload, seen)
        data["notes"] = self._serialize_value(self.notes, seen)
        data["sources"] = self._serialize_value(self.sources, seen)
        data["extras"] = self._serialize_value(self.extras, seen)

        return data

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------
    def _serialize_value(self, value: Any, seen: Set[int]) -> Any:
        """
        Recursively convert `value` into JSON-serializable structures.

        Handles:
        - BaseEntity → pointer string (to avoid deep cycles)
        - dataclasses → dict via asdict()
        - Pydantic models → dict via model_dump()
        - dict / list / tuple / set → recursively serialized
        - primitives left as-is
        """
        # Avoid infinite recursion for container cycles
        vid = id(value)
        if vid in seen:
            # If there's a deep cycle, just give a marker string.
            return "<cycle>"
        # Only mark containers / complex types
        complex_type = isinstance(value, (dict, list, tuple, set)) or is_dataclass(value) or isinstance(
            value, (BaseEntity, PydanticBaseModel)
        )
        if complex_type:
            seen.add(vid)

        # BaseEntity → pointer string (no deep recursion here)
        if isinstance(value, BaseEntity):
            return value.pointer

        # Pydantic model → dict
        if isinstance(value, PydanticBaseModel):
            try:
                return value.model_dump()
            except Exception:
                log.exception("Failed to model_dump Pydantic object %r", value)
                return repr(value)

        # Dataclass → dict
        if is_dataclass(value) and not isinstance(value, type):
            try:
                return asdict(value)
            except Exception:
                log.exception("Failed to asdict() dataclass %r", value)
                return repr(value)

        # Dict → dict of serialized values
        if isinstance(value, dict):
            return {k: self._serialize_value(v, seen) for k, v in value.items()}

        # Iterable containers → list of serialized values
        if isinstance(value, (list, tuple, set)):
            return [self._serialize_value(v, seen) for v in value]

        # Primitive / unknown → return as-is (must be JSON-serializable upstream)
        return value
