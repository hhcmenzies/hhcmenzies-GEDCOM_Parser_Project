"""
C.24.4.7 — Name Identity Enhancement

Consumes the output of xref_resolver and:
  - Ensures each INDI has a stable name identity block.
  - Builds a global name_index mapping normalized_name -> cluster data.
  - Follows extractor.py + name.py rules with no side effects.

Input:  export_xref.json
Output: export_name.json (or user-specified)

Notes:
  - This module does NOT assign new UUIDs for individuals.
    Those come from extractor.py + uuid_factory.py.
  - Name UUIDs come from uuid_for_name() using the normalized full name.
"""


from __future__ import annotations
import argparse
import json
from typing import Any, Dict

from gedcom_parser.identity.uuid_factory import uuid_for_name


# -------------------------------------------------------------
# MAIN ENRICHMENT LOGIC
# -------------------------------------------------------------

def enhance_names(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Takes loaded export_xref JSON and enriches individuals
    with cross-linked name identity blocks.

    Also builds:
        data["name_index"] = {
            normalized_full: {
                "individuals": [uuid1, uuid2, ...],
                "occurrences": int
            }
        }
    """

    individuals = data.get("individuals", {})
    name_index: Dict[str, Dict[str, Any]] = {}

    for ptr, indi in individuals.items():

        facts = indi.get("facts") or indi  # fallback if structure differs
        name_block = facts.get("name_block")

        # If missing or malformed, skip
        if not isinstance(name_block, dict):
            continue

        full_norm = name_block.get("full_name_normalized")
        full_raw = name_block.get("full")

        # Skip individuals with no usable name
        if not full_norm:
            continue

        # Generate deterministic UUID for the name identity itself
        # using uuid_for_name(pointer, normalized_full)
        # (pointer may be None if missing; uuid_for_name handles gracefully)
        name_uuid = uuid_for_name(
            facts.get("uuid"),  # INDI's UUID
            full_norm
        )

        facts["name_identity"] = {
            "full": full_raw,
            "normalized": full_norm,
            "cluster_key": full_norm,
            "uuid": name_uuid,
        }

        # Populate global index
        entry = name_index.setdefault(full_norm, {
            "individuals": [],
            "occurrences": 0
        })

        entry["individuals"].append(facts.get("uuid"))
        entry["occurrences"] += 1

    data["name_index"] = name_index
    return data


# -------------------------------------------------------------
# CLI WRAPPER
# -------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="C.24.4.7 — Name identity enrichment"
    )
    ap.add_argument("input", help="Input export_xref.json")
    ap.add_argument("-o", "--output", default="outputs/export_name.json")
    args = ap.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    data = enhance_names(data)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"[INFO] Name identity enhancement complete.")
    print(f"[INFO] Enhanced export written to: {args.output}")


if __name__ == "__main__":
    main()
