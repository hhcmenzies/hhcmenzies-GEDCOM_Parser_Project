"""
C.24.4.7 – Cross-Reference Resolver / UUID Mapper

Takes the base export produced by gedcom_parser.main (which contains
fully-extracted INDI/FAM/SOUR/REPO/OBJE records), then:

1. Ensures every record type has a proper deterministic UUID.
2. Builds a uuid_index:
       { "INDI": {pointer → uuid}, ... }
3. Resolves all INDI relationships (FAMC/FAMS) to UUIDs.
4. Resolves all FAM members (HUSB/WIFE/CHIL) to UUIDs.
5. Writes an enhanced export (default: outputs/export_xref.json).
"""

from __future__ import annotations

import argparse
import json
import logging
from typing import Any, Dict, List, Optional

from gedcom_parser.identity.uuid_factory import uuid_for_pointer
from gedcom_parser.logging import get_logger

log = get_logger("xref_resolver")


# =====================================================================
# UUID INDEX
# =====================================================================

def build_uuid_index(root: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    """
    Scans all individuals, families, sources, repositories, and objects
    and ensures each one has a deterministic UUID, using uuid_for_pointer().

    Returns:
        { "INDI": {pointer: uuid}, ... }

    Also backfills uuid fields inside the records where missing.
    """

    uuid_index: Dict[str, Dict[str, str]] = {
        "INDI": {},
        "FAM": {},
        "SOUR": {},
        "REPO": {},
        "OBJE": {},
    }

    sections = {
        "INDI": root.get("individuals", {}),
        "FAM":  root.get("families", {}),
        "SOUR": root.get("sources", {}),
        "REPO": root.get("repositories", {}),
        "OBJE": root.get("media", {}),
    }

    for rec_type, group in sections.items():
        for ptr, record in group.items():
            facts = record.get("facts", {}) or {}
            cur_uuid = facts.get("uuid")

            # Guarantee a UUID
            new_uuid = cur_uuid or uuid_for_pointer(rec_type, ptr)

            # Save into the facts block
            facts["uuid"] = new_uuid
            record["facts"] = facts

            # Save in the index
            uuid_index[rec_type][ptr] = new_uuid

    return uuid_index


# =====================================================================
# INDI RELATIONSHIP RESOLUTION
# =====================================================================

def resolve_indi_relationships(
    individuals: Dict[str, Any],
    uuid_index: Dict[str, Dict[str, str]],
) -> None:
    """
    Converts:
        facts["relationships"] = { "FAMC": ["@F123@"], ... }

    Into:
        facts["relationships_resolved"] = {
            "FAMC": [ { "pointer": "@F123@", "uuid": "...", "type": "FAM"} ],
            ...
        }
    """

    fam_map = uuid_index.get("FAM", {})

    for ptr, indi in individuals.items():
        facts = indi.get("facts", {}) or {}
        rel = facts.get("relationships", {}) or {}

        resolved = {"FAMC": [], "FAMS": []}

        # FAMC
        for fam_ptr in rel.get("FAMC", []):
            resolved["FAMC"].append({
                "pointer": fam_ptr,
                "uuid": fam_map.get(fam_ptr),
                "type": "FAM",
            })

        # FAMS
        for fam_ptr in rel.get("FAMS", []):
            resolved["FAMS"].append({
                "pointer": fam_ptr,
                "uuid": fam_map.get(fam_ptr),
                "type": "FAM",
            })

        facts["relationships_resolved"] = resolved
        indi["facts"] = facts


# =====================================================================
# FAMILY MEMBER RESOLUTION
# =====================================================================

def resolve_family_members(
    families: Dict[str, Any],
    uuid_index: Dict[str, Dict[str, str]],
) -> None:
    """
    Converts:
        facts["members"] = {"husband": "@I123@", "wife": ..., "children": [...]}

    Into:
        facts["members_resolved"] = {
            "husband": {"pointer": "@I123@", "uuid": "..."},
            "wife": {...},
            "children": [{...}, {...}]
        }
    """

    indi_map = uuid_index.get("INDI", {})

    for ptr, fam in families.items():
        facts = fam.get("facts", {}) or {}
        members = facts.get("members", {}) or {}

        resolved = {
            "husband": None,
            "wife": None,
            "children": [],
        }

        # Husband
        h = members.get("husband")
        if h:
            resolved["husband"] = {
                "pointer": h,
                "uuid": indi_map.get(h),
                "type": "INDI",
            }

        # Wife
        w = members.get("wife")
        if w:
            resolved["wife"] = {
                "pointer": w,
                "uuid": indi_map.get(w),
                "type": "INDI",
            }

        # Children
        for c in members.get("children", []):
            resolved["children"].append({
                "pointer": c,
                "uuid": indi_map.get(c),
                "type": "INDI",
            })

        facts["members_resolved"] = resolved
        fam["facts"] = facts


# =====================================================================
# MAIN RESOLUTION DRIVER
# =====================================================================

def resolve(root: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply UUID mapping and relationship resolution to the export JSON.
    """
    uuid_index = build_uuid_index(root)
    resolve_indi_relationships(root.get("individuals", {}), uuid_index)
    resolve_family_members(root.get("families", {}), uuid_index)

    root["uuid_index"] = uuid_index
    return root


# =====================================================================
# CLI DRIVER
# =====================================================================

def main(argv: Optional[List[str]] = None) -> None:
    ap = argparse.ArgumentParser(
        description="C.24.4.7 – XREF/UUID resolver for GEDCOM exports."
    )
    ap.add_argument(
        "input",
        nargs="?",
        help="Input export.json from main extractor",
    )
    ap.add_argument(
        "-i",
        "--input",
        dest="input_path",
        help="Input export.json from main extractor",
    )
    ap.add_argument(
        "-o",
        "--output",
        default="outputs/export_xref.json",
        help="Output XREF-enhanced JSON",
    )
    ap.add_argument(
        "--debug",
        action="store_true",
        help="Enable DEBUG logging",
    )

    args = ap.parse_args(argv)

    if args.debug:
        log.setLevel(logging.DEBUG)
        log.debug("Debug logging enabled for xref_resolver")

    input_path = args.input_path or args.input
    if not input_path:
        ap.error("No input specified. Use positional INPUT or -i/--input.")

    log.info("Starting XREF/UUID resolver. Input=%s Output=%s", input_path, args.output)

    with open(input_path, "r", encoding="utf-8") as f:
        root = json.load(f)

    enhanced = resolve(root)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(enhanced, f, indent=2, ensure_ascii=False)

    ui = enhanced.get("uuid_index", {})

    msg = (
        "XREF/UUID resolver complete. "
        f"INDI={len(ui.get('INDI', {}))}, "
        f"FAM={len(ui.get('FAM', {}))}, "
        f"SOUR={len(ui.get('SOUR', {}))}, "
        f"REPO={len(ui.get('REPO', {}))}, "
        f"OBJE={len(ui.get('OBJE', {}))}"
    )
    log.info(msg)
    log.info("XREF export written to: %s", args.output)

    print(f"[INFO] {msg}")
    print(f"[INFO] XREF export written to: {args.output}")


if __name__ == "__main__":
    main()
