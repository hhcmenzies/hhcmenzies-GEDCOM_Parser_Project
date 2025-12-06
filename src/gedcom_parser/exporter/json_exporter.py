"""
json_exporter.py
Unified JSON export module WITH integrated name normalization.

This module replaces the old exporter behavior by:
- Accepting an EntityRegistry instance.
- Injecting name_block (ParsedName + NormalizedName) for every individual.
- Serializing the registry to JSON in a stable and consistent format.

Called by main.py as part of the standard pipeline.
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict

from gedcom_parser.logger import get_logger
from gedcom_parser.normalization.name_normalization import (
    build_name_block_from_gedcom
)

log = get_logger("json_exporter")


def _normalize_individual_names(individuals: Dict[str, Dict[str, Any]]) -> None:
    """
    Mutates each individual in-place by adding a normalized name_block.
    Uses hybrid name parsing: raw NAME + child tags.
    """

    for indi_id, indi in individuals.items():
        # There should always be at least one NAME
        raw_names = indi.get("names", [])
        name_children = indi.get("raw_children", [])

        if not raw_names:
            log.warning(f"Individual {indi_id} has no NAME tag.")
            continue

        # Use the first NAME (GEDCOM allows multiple)
        primary_raw = raw_names[0]

        # Extract child tags belonging to NAME (GIVN, SURN, etc.)
        name_child_nodes = []
        for child in name_children:
            if child.get("tag") == "NAME":
                name_child_nodes = child.get("children", [])
                break

        try:
            block = build_name_block_from_gedcom(primary_raw, name_child_nodes)

            if block is None:
                log.warning(f"Name normalization failed for {indi_id}")
                continue

            indi["name_block"] = block.model_dump()

        except Exception as exc:
            log.exception(
                f"Error generating name_block for {indi_id}: {exc}"
            )


def export_registry_to_json(registry, output_path: str) -> None:
    """
    Main export function used by main.py

    Steps:
      1. Normalize all individual names → name_block
      2. Build JSON dictionary
      3. Write final JSON output
    """

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    log.info(f"Exporting registry JSON to: {output}")

    # STEP 1 — Insert normalized name_block
    _normalize_individual_names(registry.individuals)

    # STEP 2 — Construct output dictionary
    root_dict = {
        "individuals": registry.individuals,
        "families": registry.families,
        "sources": registry.sources,
        "repositories": registry.repositories,
        "media_objects": registry.media_objects,
        "uuid_index": registry.uuid_index,
    }

    # STEP 3 — Serialize to disk
    try:
        with open(output, "w", encoding="utf-8") as f:
            json.dump(
                root_dict,
                f,
                indent=2,
                ensure_ascii=False,
            )
    except Exception:
        log.exception("JSON export failed.")
        raise

    size = output.stat().st_size
    log.info(f"JSON export complete. size={size} bytes")
