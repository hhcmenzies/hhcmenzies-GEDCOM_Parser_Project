#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple


def read_json(p: Path) -> Any:
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(p: Path, obj: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=True)


def norm(x: Any) -> str:
    return str(x).strip().upper()


def load_paths(placements_file: Path) -> Set[str]:
    raw = read_json(placements_file)
    pl = raw["placements"] if isinstance(raw, dict) and "placements" in raw else raw
    out: Set[str] = set()
    for p in pl:
        if isinstance(p, dict) and "context_path" in p:
            out.add(norm(p["context_path"]))
        elif isinstance(p, str):
            out.add(norm(p))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a traversable production graph from placement dotpaths (prefix graph).")
    ap.add_argument("--placements", required=True, type=Path, help="Placements file (has placements[].context_path)")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--report-dir", required=True, type=Path)
    ap.add_argument("--no-timestamp", action="store_true")
    args = ap.parse_args()

    paths = load_paths(args.placements)

    # Build adjacency from prefixes: PARENT -> set(CHILD_TAG)
    children_map: Dict[str, Set[str]] = defaultdict(set)
    roots: Set[str] = set()

    for cp in paths:
        parts = cp.split(".")
        if not parts:
            continue
        roots.add(parts[0])
        # For each prefix, add the next tag
        for i in range(1, len(parts)):
            parent = ".".join(parts[:i])
            child_tag = parts[i]
            children_map[parent].add(child_tag)

    # Ensure roots exist as nodes even if they have no children
    for r in roots:
        children_map.setdefault(r, set())

    productions: Dict[str, Dict[str, Any]] = {}
    edge_count = 0

    for parent_path, child_tags in children_map.items():
        kids: List[Dict[str, Any]] = []
        for tag in sorted(child_tags):
            edge_count += 1
            child_path = f"{parent_path}.{tag}"
            kids.append({
                "tag": tag,
                "min": 0,
                "max": "M",
                "level_delta": 1,
                # THIS is the key: child production is the child prefix path
                "child_production": child_path,
            })
        productions[parent_path] = {"children": kids}

    out_graph = {
        "meta": {
            "source": str(args.placements),
            "generated_at": (datetime.utcnow().isoformat(timespec="seconds")+"Z") if not args.no_timestamp else None,
            "build": "prefix_graph_from_placements",
        },
        "record_roots": sorted(roots),
        # Identity: record root tag maps to the same production key (the root prefix)
        "root_tag_map": {r: r for r in sorted(roots)},
        "productions": productions,
    }

    args.report_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "stats": {
            "paths_in": len(paths),
            "record_roots": len(roots),
            "productions_out": len(productions),
            "edges_out": edge_count,
        },
        "record_roots": sorted(roots),
    }

    write_json(args.out, out_graph)
    write_json(args.report_dir / "prefix_graph_report.json", report)

    print(f"Wrote graph: {args.out}")
    print(f"Paths in: {len(paths)}")
    print(f"Productions: {len(productions)}  Edges: {edge_count}  Roots: {len(roots)}")
    print(f"Wrote report: {args.report_dir / 'prefix_graph_report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
