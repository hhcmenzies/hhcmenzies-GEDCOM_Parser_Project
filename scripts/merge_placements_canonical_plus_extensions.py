#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple


def read_json(p: Path) -> Any:
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(p: Path, obj: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=True)


def norm(x: Any) -> str:
    return str(x).strip().upper()


def load_placements(file: Path) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Any]]:
    raw = read_json(file)
    meta = raw.get("meta", {}) if isinstance(raw, dict) else {}
    pl = raw.get("placements") if isinstance(raw, dict) and "placements" in raw else raw
    out: Dict[str, Dict[str, Any]] = {}
    if not isinstance(pl, list):
        return out, meta
    for p in pl:
        if not isinstance(p, dict):
            continue
        cp = norm(p.get("context_path") or "")
        if not cp:
            continue
        # normalize key fields a bit
        p2 = dict(p)
        p2["context_path"] = cp
        if p2.get("parent_path"):
            p2["parent_path"] = norm(p2["parent_path"])
        if p2.get("record_root"):
            p2["record_root"] = norm(p2["record_root"])
        if p2.get("tag"):
            p2["tag"] = norm(p2["tag"])
        out[cp] = p2
    return out, meta


def main() -> int:
    ap = argparse.ArgumentParser(description="Merge canonical placements + extension placements into one unified grammar placements file.")
    ap.add_argument("--canonical", required=True, type=Path)
    ap.add_argument("--extension", action="append", required=True, type=Path, help="May be specified multiple times.")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--report", required=True, type=Path)
    ap.add_argument("--no-timestamp", action="store_true")
    args = ap.parse_args()

    canon_map, canon_meta = load_placements(args.canonical)

    merged: Dict[str, Dict[str, Any]] = dict(canon_map)
    collisions = 0
    extension_added = 0
    extension_total = 0
    overwritten_by_extension = 0
    overwrite_examples: List[Dict[str, Any]] = []

    # Merge rule:
    # - Canonical wins by default.
    # - Extension adds only new context_paths.
    # This avoids vendor paths accidentally overriding canonical grammar.
    for ext_path in args.extension:
        ext_map, ext_meta = load_placements(ext_path)
        extension_total += len(ext_map)
        for cp, p in ext_map.items():
            if cp in merged:
                collisions += 1
                # keep canonical; record a few examples
                if len(overwrite_examples) < 20:
                    overwrite_examples.append(
                        {
                            "context_path": cp,
                            "kept": "canonical",
                            "canonical_provenance": merged[cp].get("provenance") or merged[cp].get("expanded_from"),
                            "extension_provenance": p.get("provenance") or p.get("expanded_from"),
                            "extension_source": str(ext_path),
                        }
                    )
                continue
            merged[cp] = p
            extension_added += 1

    merged_list = [merged[k] for k in sorted(merged.keys())]

    out_meta: Dict[str, Any] = {
        "source_canonical": str(args.canonical),
        "source_extensions": [str(x) for x in args.extension],
        "generated_at": None if args.no_timestamp else datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "note": "Merged canonical backbone placements with vendor extension placements (Option A). Canonical wins on collisions.",
        "canonical_meta": canon_meta,
    }

    out_obj = {"meta": out_meta, "placements": merged_list}

    report = {
        "stats": {
            "canonical_in": len(canon_map),
            "extension_total_in": extension_total,
            "extension_added": extension_added,
            "collisions": collisions,
            "out_total": len(merged_list),
        },
        "examples": {
            "collision_examples_top20": overwrite_examples,
        },
    }

    write_json(args.out, out_obj)
    write_json(args.report, report)

    print(f"Wrote merged placements: {args.out} (total={len(merged_list)})")
    print(f"Wrote merge report:     {args.report} (collisions={collisions}, ext_added={extension_added})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
