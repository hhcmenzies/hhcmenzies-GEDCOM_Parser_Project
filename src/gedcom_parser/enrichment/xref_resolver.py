"""
C.24.4.7 – Cross-Reference Resolver / UUID Mapper (Modern Export Schema)

Modern assumptions:
- export.json contains top-level dicts:
    individuals, families, sources, repositories, media_objects
- each record is a dict (NOT stringified dataclasses)
- records may or may not already contain a UUID
"""

from __future__ import annotations

import argparse
import json
import logging
from typing import Any, Dict, List, Optional

from gedcom_parser.identity.uuid_factory import uuid_for_pointer
from gedcom_parser.logger import get_logger

log = get_logger("xref_resolver")


def _ensure_dict(x: Any) -> Dict[str, Any]:
    """Return x if it's a dict, else an empty dict."""
    return x if isinstance(x, dict) else {}


def _get_record_uuid(record: Dict[str, Any]) -> Optional[str]:
    """
    Modern exports may store uuid in:
      - record["uuid"]
      - record["facts"]["uuid"]   (legacy-ish pipeline blocks)
    We support both, preferring record["uuid"].
    """
    if isinstance(record.get("uuid"), str) and record["uuid"].strip():
        return record["uuid"].strip()

    facts = record.get("facts")
    if isinstance(facts, dict):
        u = facts.get("uuid")
        if isinstance(u, str) and u.strip():
            return u.strip()

    return None


def _set_record_uuid(record: Dict[str, Any], uuid_val: str) -> None:
    """
    Write UUID in modern location + preserve facts.uuid if facts block exists.
    """
    record["uuid"] = uuid_val

    facts = record.get("facts")
    if isinstance(facts, dict):
        facts["uuid"] = uuid_val
        record["facts"] = facts


def build_uuid_index(root: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    """
    Build uuid_index = { "INDI": {ptr:uuid}, "FAM":..., "OBJE":... }

    Also backfills UUIDs into records when missing.
    """
    uuid_index: Dict[str, Dict[str, str]] = {
        "INDI": {},
        "FAM": {},
        "SOUR": {},
        "REPO": {},
        "OBJE": {},
    }

    individuals = _ensure_dict(root.get("individuals"))
    families = _ensure_dict(root.get("families"))
    sources = _ensure_dict(root.get("sources"))
    repositories = _ensure_dict(root.get("repositories"))

    # Modern key
    media_objects = _ensure_dict(root.get("media_objects"))

    # Backward compat (if any older exports still use it)
    legacy_media = _ensure_dict(root.get("media"))

    # Prefer modern media_objects; merge legacy as fallback without overwriting
    for k, v in legacy_media.items():
        if k not in media_objects:
            media_objects[k] = v

    sections: Dict[str, Dict[str, Any]] = {
        "INDI": individuals,
        "FAM": families,
        "SOUR": sources,
        "REPO": repositories,
        "OBJE": media_objects,
    }

    for rec_type, group in sections.items():
        for ptr, record in group.items():
            if not isinstance(record, dict):
                # Modern pipeline expects dicts; skip anything else safely.
                continue

            cur_uuid = _get_record_uuid(record)
            new_uuid = cur_uuid or uuid_for_pointer(rec_type, ptr)

            _set_record_uuid(record, new_uuid)
            uuid_index[rec_type][ptr] = new_uuid

    return uuid_index


def resolve_indi_relationships(
    individuals: Dict[str, Any],
    uuid_index: Dict[str, Dict[str, str]],
) -> None:
    """
    Resolve INDI relationships (FAMC/FAMS) to UUIDs.

    Supports modern + legacy layouts:
    - Modern: individuals[*]["families_as_child"] / ["families_as_spouse"]
    - Legacy: individuals[*]["facts"]["relationships"]["FAMC"/"FAMS"]
    Writes a normalized output under individuals[*]["relationships_resolved"].
    """
    fam_map = uuid_index.get("FAM", {})

    for ptr, indi in individuals.items():
        if not isinstance(indi, dict):
            continue

        famc_list: List[str] = []
        fams_list: List[str] = []

        # Modern
        if isinstance(indi.get("families_as_child"), list):
            famc_list = [x for x in indi["families_as_child"] if isinstance(x, str)]
        if isinstance(indi.get("families_as_spouse"), list):
            fams_list = [x for x in indi["families_as_spouse"] if isinstance(x, str)]

        # Legacy facts.relationships fallback
        facts = indi.get("facts")
        if isinstance(facts, dict):
            rel = facts.get("relationships")
            if isinstance(rel, dict):
                famc_list = famc_list or [x for x in rel.get("FAMC", []) if isinstance(x, str)]
                fams_list = fams_list or [x for x in rel.get("FAMS", []) if isinstance(x, str)]

        resolved = {
            "FAMC": [{"pointer": p, "uuid": fam_map.get(p), "type": "FAM"} for p in famc_list],
            "FAMS": [{"pointer": p, "uuid": fam_map.get(p), "type": "FAM"} for p in fams_list],
        }

        indi["relationships_resolved"] = resolved


def resolve_family_members(
    families: Dict[str, Any],
    uuid_index: Dict[str, Dict[str, str]],
) -> None:
    """
    Resolve family members (husband/wife/children) to UUIDs.

    Supports modern + legacy layouts:
    - Modern: families[*]["husband"], ["wife"], ["children"]
    - Legacy: families[*]["facts"]["members"]
    Writes families[*]["members_resolved"].
    """
    indi_map = uuid_index.get("INDI", {})

    for ptr, fam in families.items():
        if not isinstance(fam, dict):
            continue

        husband = fam.get("husband") if isinstance(fam.get("husband"), str) else None
        wife = fam.get("wife") if isinstance(fam.get("wife"), str) else None
        children = fam.get("children") if isinstance(fam.get("children"), list) else []

        # Legacy fallback
        facts = fam.get("facts")
        if isinstance(facts, dict) and isinstance(facts.get("members"), dict):
            mem = facts["members"]
            husband = husband or (mem.get("husband") if isinstance(mem.get("husband"), str) else None)
            wife = wife or (mem.get("wife") if isinstance(mem.get("wife"), str) else None)
            if not children:
                children = mem.get("children") if isinstance(mem.get("children"), list) else []

        resolved = {
            "husband": {"pointer": husband, "uuid": indi_map.get(husband), "type": "INDI"} if husband else None,
            "wife": {"pointer": wife, "uuid": indi_map.get(wife), "type": "INDI"} if wife else None,
            "children": [
                {"pointer": c, "uuid": indi_map.get(c), "type": "INDI"}
                for c in children
                if isinstance(c, str)
            ],
        }

        fam["members_resolved"] = resolved


def resolve(root: Dict[str, Any]) -> Dict[str, Any]:
    uuid_index = build_uuid_index(root)

    resolve_indi_relationships(_ensure_dict(root.get("individuals")), uuid_index)
    resolve_family_members(_ensure_dict(root.get("families")), uuid_index)

    root["uuid_index"] = uuid_index
    return root


def main(argv: Optional[List[str]] = None) -> None:
    ap = argparse.ArgumentParser(description="C.24.4.7 – XREF/UUID resolver (modern schema).")
    ap.add_argument("input", nargs="?", help="Input export.json from main extractor")
    ap.add_argument("-i", "--input", dest="input_path", help="Input export.json from main extractor")
    ap.add_argument("-o", "--output", default="outputs/export_xref.json", help="Output XREF-enhanced JSON")
    ap.add_argument("--debug", action="store_true", help="Enable DEBUG logging")

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
        "XREF complete. "
        f"INDI={len(ui.get('INDI', {}))} "
        f"FAM={len(ui.get('FAM', {}))} "
        f"SOUR={len(ui.get('SOUR', {}))} "
        f"REPO={len(ui.get('REPO', {}))} "
        f"OBJE={len(ui.get('OBJE', {}))}"
    )
    log.info(msg)
    print(f"[INFO] {msg}")
    print(f"[INFO] XREF export written to: {args.output}")


if __name__ == "__main__":
    main()
