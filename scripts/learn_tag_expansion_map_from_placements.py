#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
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

def last_tag(path: Any) -> str:
    if not path:
        return ""
    s = norm(path)
    if "." in s:
        return s.split(".")[-1]
    return s

def main() -> int:
    ap = argparse.ArgumentParser(description="Learn (parent_tag, child_tag) -> child_production from canonical placements.")
    ap.add_argument("--placements", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--report-dir", required=True, type=Path)
    args = ap.parse_args()

    raw = read_json(args.placements)
    pl = raw["placements"] if isinstance(raw, dict) and "placements" in raw else raw

    # map[parent_tag][child_tag] = Counter(child_production)
    m: Dict[str, Dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))

    used = 0
    skipped = 0

    for p in pl:
        if not isinstance(p, dict):
            continue
        child_tag = norm(p.get("tag"))
        parent_tag = last_tag(p.get("parent_path"))
        child_prod = norm(p.get("source_production"))

        if not parent_tag or not child_tag:
            skipped += 1
            continue
        if not child_prod or child_prod in ("UNKNOWN","NONE","NULL"):
            skipped += 1
            continue

        m[parent_tag][child_tag][child_prod] += 1
        used += 1

    out_map: Dict[str, Dict[str, str]] = {}
    conflicts = []

    for parent_tag, kids in m.items():
        out_map[parent_tag] = {}
        for child_tag, c in kids.items():
            best, best_n = c.most_common(1)[0]
            out_map[parent_tag][child_tag] = best
            if len(c) > 1:
                conflicts.append([parent_tag, child_tag, c.most_common(5)])

    args.report_dir.mkdir(parents=True, exist_ok=True)
    write_json(args.out, {"map": out_map})

    write_json(args.report_dir / "tag_expansion_map_report.json", {
        "stats": {
            "placements_used": used,
            "placements_skipped": skipped,
            "parent_tags": len(out_map),
            "pairs_total": sum(len(v) for v in out_map.values()),
            "pairs_with_conflicts": len(conflicts),
        },
        "conflicts_top30": conflicts[:30],
    })

    print(f"Wrote: {args.out}")
    print(f"Wrote report: {args.report_dir / 'tag_expansion_map_report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
