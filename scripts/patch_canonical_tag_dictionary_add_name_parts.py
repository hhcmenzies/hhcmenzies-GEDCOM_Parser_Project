#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


def read_json(p: Path) -> Any:
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)

def write_json(p: Path, obj: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=True)

def norm(x: Any) -> str:
    return str(x).strip().upper()

def ensure_tag_container(raw: Any) -> Dict[str, Any]:
    """
    Normalize into shape:
      {"tags": {TAG: meta, ...}, "meta": {...}}
    """
    if isinstance(raw, dict) and "tags" in raw and isinstance(raw["tags"], dict):
        if "meta" not in raw:
            raw["meta"] = {}
        return raw
    if isinstance(raw, dict):
        # assume raw itself is the tag dict
        return {"tags": raw, "meta": {}}
    raise SystemExit("Unsupported canonical tag dictionary JSON shape")

def main() -> int:
    ap = argparse.ArgumentParser(description="Patch canonical tag dictionary with missing standard NAME-part tags (e.g., GIVN).")
    ap.add_argument("--in", dest="inp", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--no-timestamp", action="store_true")
    args = ap.parse_args()

    raw = read_json(args.inp)
    obj = ensure_tag_container(raw)
    tags: Dict[str, Any] = obj["tags"]

    # Standard GEDCOM name-part tags commonly seen in exports
    name_part_tags = [
        "GIVN",  # Given name
        "SURN",  # Surname
        "NPFX",  # Name prefix
        "NSFX",  # Name suffix
        "NICK",  # Nickname
    ]

    added = []
    for t in name_part_tags:
        T = norm(t)
        if T in (norm(k) for k in tags.keys()):
            # If keys aren't normalized, we still treat it as present
            # But to be safe, also check direct
            if T in tags:
                continue
            # present under different case -> skip adding duplicate
            continue

        tags[T] = {
            "status": "ADDED_BY_PATCH",
            "notes": "Added to avoid misclassifying standard NAME-part tags as unknown.",
            "provenance": "patch_canonical_tag_dictionary_add_name_parts",
        }
        added.append(T)

    meta = obj.get("meta", {}) or {}
    meta["patched_by"] = "patch_canonical_tag_dictionary_add_name_parts"
    meta["patched_at"] = (datetime.utcnow().isoformat(timespec="seconds") + "Z") if not args.no_timestamp else None
    meta["added_tags"] = added
    obj["meta"] = meta

    write_json(args.out, obj)

    print(f"Wrote patched canonical tag dictionary: {args.out}")
    print(f"Added tags: {len(added)} -> {added}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
