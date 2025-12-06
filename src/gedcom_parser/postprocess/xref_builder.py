from __future__ import annotations

"""
C.24.4.7 — Crosslink / Referential Integrity Post-Processor

Reads an export JSON (from gedcom_parser.main), walks all entities, and:

1. Builds a global uuid_index:
    {
      "INDI": { "<uuid>": "<@I...@>", ... },
      "FAM":  { "<uuid>": "<@F...@>", ... },
      "SOUR": { "<uuid>": "<@S...@>", ... },
      "REPO": { ... },
      "OBJE": { ... },
    }

2. Attaches resolved relationships on individuals:
    facts["relationships_resolved"] = {
      "FAMC": [ {"pointer": "@F1@", "uuid": "<fam-uuid>"}, ... ],
      "FAMS": [ {"pointer": "@F2@", "uuid": "<fam-uuid>"}, ... ],
    }

3. Attaches resolved members on families:
    facts["members_resolved"] = {
      "husband": {"pointer": "@I1@", "uuid": "<indi-uuid>"} or None,
      "wife":    {"pointer": "@I2@", "uuid": "<indi-uuid>"} or None,
      "children": [
        {"pointer": "@I3@", "uuid": "<indi-uuid>"},
        ...
      ],
    }

Writes final output to: outputs/export_xref.json
"""

import argparse
import json
from typing import Any, Dict, Optional


# ============================================================
# Helpers
# ============================================================

def _entity_dict(data: Dict[str, Any], key: str) -> Dict[str, Any]:
    """Safely fetch dict for a given top-level key."""
    block = data.get(key)
    if not isinstance(block, dict):
        return {}
    return block


def _get_uuid(entry: Dict[str, Any]) -> Optional[str]:
    """Return entry.facts.uuid if present."""
    if not isinstance(entry, dict):
        return None
    facts = entry.get("facts")
    if not isinstance(facts, dict):
        return None
    return facts.get("uuid")


def _resolve_pointer(ptr: str, entity_dict: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """Map '@Ixxx@' → uuid."""
    target = entity_dict.get(ptr)
    if not target:
        return {"pointer": ptr, "uuid": None}
    return {"pointer": ptr, "uuid": _get_uuid(target)}


# ============================================================
# XREF BUILDER CORE
# ============================================================

def build_uuid_index(data: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    """
    Build:
        uuid_index["INDI"][uuid] = pointer
        uuid_index["FAM"][uuid]  = pointer
        etc.
    """
    uuid_index = {
        "INDI": {},
        "FAM": {},
        "SOUR": {},
        "REPO": {},
        "OBJE": {},
    }

    for key, block in uuid_index.items():
        entity_block = _entity_dict(data, key.lower() + "s")
        for ptr, entry in entity_block.items():
            u = _get_uuid(entry)
            if u:
                block[u] = ptr

    return uuid_index


def resolve_individuals(data: Dict[str, Any]) -> None:
    """Attach relationships_resolved to individuals."""
    inds = _entity_dict(data, "individuals")
    fams = _entity_dict(data, "families")

    for ptr, indi in inds.items():
        facts = indi.get("facts", {})
        rel = facts.get("relationships", {})

        resolved = {
            "FAMC": [],
            "FAMS": [],
        }

        for fam_ptr in rel.get("FAMC", []):
            resolved["FAMC"].append(_resolve_pointer(fam_ptr, fams))

        for fam_ptr in rel.get("FAMS", []):
            resolved["FAMS"].append(_resolve_pointer(fam_ptr, fams))

        facts["relationships_resolved"] = resolved


def resolve_families(data: Dict[str, Any]) -> None:
    """Attach members_resolved to families."""
    inds = _entity_dict(data, "individuals")
    fams = _entity_dict(data, "families")

    for ptr, fam in fams.items():
        facts = fam.get("facts", {})
        mem = facts.get("members", {})

        resolved = {
            "husband": None,
            "wife": None,
            "children": [],
        }

        h_ptr = mem.get("husband")
        w_ptr = mem.get("wife")
        children_ptrs = mem.get("children", [])

        if h_ptr:
            resolved["husband"] = _resolve_pointer(h_ptr, inds)
        if w_ptr:
            resolved["wife"] = _resolve_pointer(w_ptr, inds)

        for c in children_ptrs:
            resolved["children"].append(_resolve_pointer(c, inds))

        facts["members_resolved"] = resolved


# ============================================================
# MAIN DRIVER
# ============================================================

def run_xref(input_path: str, output_path: str) -> None:
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 1. Build global UUID index
    uuid_index = build_uuid_index(data)
    data["uuid_index"] = uuid_index

    # 2. Build resolved relationship views
    resolve_individuals(data)
    resolve_families(data)

    # 3. Write out
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"[INFO] XREF-enhanced export written to: {output_path}")


# ============================================================
# CLI
# ============================================================

def build_arg_parser():
    p = argparse.ArgumentParser(
        description="C.24.4.7 — Crosslink / Referential Integrity builder"
    )
    p.add_argument("input", help="Path to export.json")
    p.add_argument("-o", "--output",
                  help="Output path",
                  required=False,
                  default="outputs/export_xref.json")
    return p


def main():
    args = build_arg_parser().parse_args()
    run_xref(args.input, args.output)


if __name__ == "__main__":
    main()
