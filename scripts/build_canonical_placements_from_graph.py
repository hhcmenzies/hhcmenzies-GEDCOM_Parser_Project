#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, deque
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


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
        description="Build canonical placements by traversing a production graph (root_tag_map + productions)."
    )
    ap.add_argument("--production-graph", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--report-dir", required=True, type=Path)
    ap.add_argument("--max-depth", type=int, default=12)
    ap.add_argument("--max-placements", type=int, default=50000)
    ap.add_argument("--no-timestamp", action="store_true")
    args = ap.parse_args()

    g = read_json(args.production_graph)
    prods: Dict[str, Any] = g.get("productions", {}) or {}
    record_roots: List[str] = [norm(x) for x in (g.get("record_roots", []) or [])]
    root_tag_map: Dict[str, str] = {norm(k): norm(v) for k, v in (g.get("root_tag_map", {}) or {}).items()}

    if not record_roots:
        record_roots = ["HEAD","TRLR","INDI","FAM","SOUR","REPO","SUBM","SUBN","NOTE","OBJE"]

    # placements keyed by context_path
    placements: Dict[str, Dict[str, Any]] = {}

    # BFS queue entries:
    # (record_root_tag, current_context_path, current_production, current_depth, current_level)
    q = deque()

    # seed roots
    for rr in record_roots:
        # always emit the root tag itself (e.g., INDI)
        rr_path = rr
        placements[rr_path] = {
            "context_path": rr_path,
            "tag": rr,
            "level": 0,
            "min": 1,
            "max": 1,
            "parent_path": None,
            "record_root": rr,
            "expanded_from": None,
            "source_production": root_tag_map.get(rr, "UNKNOWN_ROOT_PRODUCTION"),
            "provenance": "GRAPH_TRAVERSE_ROOT",
        }

        root_prod = root_tag_map.get(rr)
        if root_prod and root_prod in prods:
            q.append((rr, rr_path, root_prod, 0, 0))

    # stats / safety
    expanded_edges = 0
    missing_production_hits = Counter()
    emitted = 0

    while q:
        rr, parent_path, parent_prod, depth, parent_level = q.popleft()

        if depth >= args.max_depth:
            continue

        body = prods.get(parent_prod)
        if not isinstance(body, dict):
            missing_production_hits[parent_prod] += 1
            continue

        children = body.get("children", []) or []
        for ch in children:
            if not isinstance(ch, dict):
                continue
            tag = norm(ch.get("tag"))
            if not tag:
                continue

            level_delta = int(ch.get("level_delta", 1) or 1)
            level = parent_level + level_delta

            cp = f"{parent_path}.{tag}"
            if cp in placements:
                # already emitted; still allow traversal by production if not done
                pass
            else:
                placements[cp] = {
                    "context_path": cp,
                    "tag": tag,
                    "level": level,
                    "min": int(ch.get("min", 0) or 0),
                    "max": str(ch.get("max", "M")),
                    "parent_path": parent_path,
                    "record_root": rr,
                    "expanded_from": parent_prod,
                    "source_production": norm(ch.get("child_production") or "UNKNOWN"),
                    "provenance": "GRAPH_TRAVERSE",
                }
                emitted += 1
                if len(placements) >= args.max_placements:
                    break

            child_prod = ch.get("child_production")
            if child_prod:
                child_prod = norm(child_prod)
                expanded_edges += 1
                if child_prod in prods:
                    q.append((rr, cp, child_prod, depth + 1, level))
                else:
                    missing_production_hits[child_prod] += 1

        if len(placements) >= args.max_placements:
            break

    out_list = sorted(placements.values(), key=lambda x: x["context_path"])

    meta = {
        "generated_at": (datetime.utcnow().isoformat(timespec="seconds") + "Z") if not args.no_timestamp else None,
        "source_graph": str(args.production_graph),
        "stats": {
            "record_roots": len(record_roots),
            "placements_out": len(out_list),
            "expanded_edges_seen": expanded_edges,
            "missing_production_keys": len(missing_production_hits),
        },
    }

    write_json(args.out, {"meta": meta, "placements": out_list})

    args.report_dir.mkdir(parents=True, exist_ok=True)
    write_json(args.report_dir / "graph_traversal_report.json", {
        "meta": meta,
        "missing_production_hits_top20": missing_production_hits.most_common(20),
    })

    # optional CSV for quick diffing
    with open(args.report_dir / "graph_traversal_paths.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["context_path","tag","record_root","level","parent_path","expanded_from","source_production","min","max"])
        for p in out_list:
            w.writerow([
                p.get("context_path",""),
                p.get("tag",""),
                p.get("record_root",""),
                p.get("level",""),
                p.get("parent_path",""),
                p.get("expanded_from",""),
                p.get("source_production",""),
                p.get("min",""),
                p.get("max",""),
            ])

    print(f"Wrote: {args.out} (placements={len(out_list)})")
    print(f"Wrote report: {args.report_dir / 'graph_traversal_report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
