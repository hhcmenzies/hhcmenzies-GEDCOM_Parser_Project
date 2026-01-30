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
    ap = argparse.ArgumentParser(description="Patch structures-derived production graph with learned (parent_prod, tag)->child_prod map.")
    ap.add_argument("--graph-in", required=True, type=Path)
    ap.add_argument("--map", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--report-dir", required=True, type=Path)
    args = ap.parse_args()

    g = read_json(args.graph_in)
    prods: Dict[str, Any] = g.get("productions", {}) or {}

    learned = read_json(args.map).get("map", {}) or {}
    learned = {norm(k): {norm(t): norm(v) for t, v in (tv or {}).items()} for k, tv in learned.items()}

    patched = 0
    total = 0
    missing = Counter()

    for parent_prod, body in prods.items():
        pp = norm(parent_prod)
        children = body.get("children", []) or []
        for ch in children:
            if not isinstance(ch, dict):
                continue
            total += 1
            tag = norm(ch.get("tag"))
            if not tag:
                continue
            # only patch if null/empty
            if ch.get("child_production"):
                continue
            cp = learned.get(pp, {}).get(tag)
            if cp:
                ch["child_production"] = cp
                patched += 1
            else:
                missing[(pp + "." + tag)] += 1

    g["meta"] = g.get("meta", {}) or {}
    g["meta"]["patched_with_learned_map"] = {
        "patched_edges": patched,
        "edges_total": total,
        "coverage": (patched / total) if total else 0.0,
    }

    write_json(args.out, g)

    args.report_dir.mkdir(parents=True, exist_ok=True)
    write_json(args.report_dir / "patch_graph_report.json", {
        "patched_edges": patched,
        "edges_total": total,
        "coverage": (patched / total) if total else 0.0,
        "missing_examples_top30": missing.most_common(30),
    })

    print(f"Wrote: {args.out}")
    print(f"Patched edges: {patched}/{total} ({(patched/total*100.0) if total else 0.0:.1f}%)")
    print(f"Wrote report: {args.report_dir / 'patch_graph_report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
