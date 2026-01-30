#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
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


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Make a production graph resolvable by ensuring all referenced child_production keys exist."
    )
    ap.add_argument("--graph-in", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--report-dir", required=True, type=Path)
    args = ap.parse_args()

    g = read_json(args.graph_in)
    prods: Dict[str, Any] = g.get("productions", {}) or {}

    # Normalize production keys
    prods_norm: Dict[str, Any] = {norm(k): v for k, v in prods.items()}

    # Ensure TRLR exists as a production node (some graphs won't have it)
    if "TRLR" not in prods_norm:
        prods_norm["TRLR"] = {"children": []}

    # Root map tells us how record tags correspond to canonical productions
    # Example: INDI -> INDIVIDUAL_RECORD, HEAD -> HEADER, etc.
    root_tag_map = {norm(k): norm(v) for k, v in (g.get("root_tag_map", {}) or {}).items()}

    # Create aliases so production keys like INDIVIDUAL_RECORD exist, by copying the tag-keyed node (INDI).
    alias_created = []
    for tag, prod in root_tag_map.items():
        if prod in prods_norm:
            continue
        if tag in prods_norm:
            prods_norm[prod] = json.loads(json.dumps(prods_norm[tag]))  # deep copy
            alias_created.append((prod, tag))

    # Now, ensure ALL referenced child_production keys exist.
    # If an expansion points to a production key that doesn't exist, we create a stub node.
    referenced = Counter()
    missing = Counter()

    for parent_prod, body in prods_norm.items():
        children = (body or {}).get("children", []) or []
        for ch in children:
            if not isinstance(ch, dict):
                continue
            cp = ch.get("child_production")
            if not cp:
                continue
            cp = norm(cp)
            referenced[cp] += 1
            if cp not in prods_norm:
                missing[cp] += 1

    stubs_created = []
    for k in missing.keys():
        # Create empty node so traversal can continue without crashing.
        prods_norm[k] = {"children": []}
        stubs_created.append(k)

    # Write output
    out = dict(g)
    out["productions"] = prods_norm

    args.report_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "stats": {
            "productions_in": len(prods),
            "productions_out": len(prods_norm),
            "aliases_created": len(alias_created),
            "stubs_created": len(stubs_created),
            "referenced_child_productions": len(referenced),
            "missing_child_productions_before": len(missing),
        },
        "aliases_created_top50": alias_created[:50],
        "stubs_created_top200": stubs_created[:200],
        "missing_child_productions_top50": missing.most_common(50),
    }

    write_json(args.out, out)
    write_json(args.report_dir / "make_graph_resolvable_report.json", report)

    print(f"Wrote: {args.out}")
    print(f"Aliases created: {len(alias_created)}")
    print(f"Stubs created: {len(stubs_created)}")
    print(f"Wrote report: {args.report_dir / 'make_graph_resolvable_report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
