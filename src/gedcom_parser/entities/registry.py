"""
Entity registry for extracted GEDCOM records.

Phase 1 – Entities backbone

This module bridges:
- The raw GEDCOM tree (root records from parser_core)
- The entity extractors (extractor.py)
- The JSON exporter (exporter/json_exporter.py)

Design:
- EntityRegistry is a simple container:
    individuals:  { pointer -> dict block from extract_indi }
    families:     { pointer -> dict block from extract_family }
    sources:      { pointer -> dict block from extract_source }
    repositories: { pointer -> dict block from extract_repository }
    media_objects:{ pointer -> dict block from extract_media_object }

- build_entity_registry(root_records) walks the top-level GEDCOM records and
  populates the registry using the existing extractors.

NOTE:
- We do not introduce BaseEntity usage yet; we keep the current JSON structure
  exactly the same to avoid breaking downstream modules (xref_resolver,
  place_standardizer, event_disambiguator, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable

from gedcom_parser.logging import get_logger

log = get_logger(__name__)


@dataclass
class EntityRegistry:
    """
    In-memory container for all extracted entity blocks.

    Each mapping is keyed by GEDCOM pointer, e.g. "@I1@", "@F23@", "@S12@".
    Values are plain dicts as returned by the entity extractors.
    """

    individuals: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    families: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    sources: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    repositories: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    media_objects: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def stats(self) -> Dict[str, int]:
        """Return simple counts for each entity category."""
        return {
            "INDI": len(self.individuals),
            "FAM": len(self.families),
            "SOUR": len(self.sources),
            "REPO": len(self.repositories),
            "OBJE": len(self.media_objects),
        }


def build_entity_registry(root_records: Iterable[Dict[str, Any]]) -> EntityRegistry:
    """
    Build an EntityRegistry from the list of top-level GEDCOM records.

    Parameters
    ----------
    root_records:
        Iterable of top-level nodes as produced by tree_builder +
        value_reconstructor. Each item is a dict with at least:
            {
                "tag": "INDI" | "FAM" | "SOUR" | "REPO" | "OBJE" | ...,
                "pointer": "@I1@" or similar,
                "children": [...],
                ...
            }

    Returns
    -------
    EntityRegistry
        Populated with extracted entities.
    """
    # Import here to avoid circular imports at module load time
    from gedcom_parser.entities.extractor import (
        extract_indi,
        extract_family,
        extract_source,
        extract_repository,
        extract_media_object,
    )

    registry = EntityRegistry()

    indi_count = fam_count = src_count = repo_count = obje_count = 0

    for node in root_records:
        tag = node.get("tag")
        pointer = node.get("pointer")

        # We only care about records that actually have pointers
        if not pointer or not isinstance(pointer, str):
            continue

        if tag == "INDI":
            block = extract_indi(node)
            registry.individuals[pointer] = block
            indi_count += 1

        elif tag == "FAM":
            block = extract_family(node)
            registry.families[pointer] = block
            fam_count += 1

        elif tag == "SOUR":
            block = extract_source(node)
            registry.sources[pointer] = block
            src_count += 1

        elif tag == "REPO":
            block = extract_repository(node)
            registry.repositories[pointer] = block
            repo_count += 1

        elif tag == "OBJE":
            block = extract_media_object(node)
            registry.media_objects[pointer] = block
            obje_count += 1

        # Other top-level tags (SUBM, HEAD, TRLR, etc.) are ignored here,
        # but still present in the raw tree and export.json if needed.

    log.info(
        "EntityRegistry built: INDI=%s, FAM=%s, SOUR=%s, REPO=%s, OBJE=%s",
        indi_count,
        fam_count,
        src_count,
        repo_count,
        obje_count,
    )

    return registry
