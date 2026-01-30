#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Tuple


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
    ap = argparse.ArgumentParser(description="Learn (parent_production, tag) -> child_production map from canonical placements.")
    ap.add_argument("--canonical-placements", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--report-dir", required=True, type=Path)
    args = ap.parse_args()

    raw = read_json(args.canonical_placements)
    pl = raw["placements"] if isinstance(raw, dict) and "placements" in raw else raw

    # map: parent_production -> tag -> Counter(child_production)
    m: Dict[str, Dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))

    used = 0
    skipped = 0
    for p in pl:
        if not isinstance(p, dict):
            continue
        tag = norm(p.get("tag"))
        parent_prod = norm(p.get("expanded_from"))  # where it came from
        child_prod = norm(p.get("source_production"))  # what it expands into
        if not tag or not parent_prod or parent_prod in ("NONE","NULL","UNKNOWN"):
            skipped += 1
            continue
        if not child_prod or child_prod in ("NONE","NULL","UNKNOWN"):
            skipped += 1
            continue
        m[parent_prod][tag][child_prod] += 1
        used += 1

    # collapse to best guess per (parent_prod, tag)
    out_map: Dict[str, Dict[str, str]] = {}
    conflicts = []
    for parent_prod, tags in m.items():
        out_map[parent_prod] = {}
        for tag, c in tags.items():
            best, best_n = c.most_common(1)[0]
            out_map[parent_prod][tag] = best
            if len(c) > 1:
                conflicts.append((parent_prod, tag, c.most_common(5)))

    args.report_dir.mkdir(parents=True, exist_ok=True)
    write_json(args.out, {"map": out_map})
    write_json(args.report_dir / "tag_to_production_map_report.json", {
        "stats": {
            "placements_used": used,
            "placements_skipped": skipped,
            "parent_productions": len(out_map),
            "pairs_total": sum(len(v) for v in out_map.values()),
            "pairs_with_conflicts": len(conflicts),
        },
        "conflicts_top20": conflicts[:20],
    })

    print(f"Wrote: {args.out}")
    print(f"Wrote report: {args.report_dir / 'tag_to_production_map_report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
