#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
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


def norm(s: Any) -> str:
    return str(s).strip().upper()


def norm_max(v: Any) -> str:
    if v is None:
        return "M"
    s = str(v).strip().upper()
    if s in ("M", "N", "*"):
        return "M"
    # numeric?
    try:
        int(s)
        return s
    except Exception:
        return "M"


def norm_min(v: Any) -> int:
    if v is None:
        return 0
    s = str(v).strip()
    try:
        return int(s)
    except Exception:
        return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Infer a production graph using canonical placements edges: expanded_from --tag--> source_production."
    )
    ap.add_argument("--canonical-placements", required=True, type=Path,
                    help="datasets/gedcom/canonical/canonical_grammar_placements_gedcom551.json (or a fuller file)")
    ap.add_argument("--out", required=True, type=Path,
                    help="Output inferred production graph JSON")
    ap.add_argument("--report-dir", required=True, type=Path)
    ap.add_argument("--no-timestamp", action="store_true")
    args = ap.parse_args()

    raw = read_json(args.canonical_placements)
    placements = raw["placements"] if isinstance(raw, dict) and "placements" in raw else raw
    if not isinstance(placements, list):
        raise SystemExit("Unsupported placements JSON shape")

    # Edge aggregation:
    # parent_prod, tag -> child_prod (choose most common if conflicts)
    edge_votes: Dict[Tuple[str, str], Counter] = defaultdict(Counter)
    edge_min: Dict[Tuple[str, str], int] = {}
    edge_max: Dict[Tuple[str, str], str] = {}

    # Root tag -> best production (source_production) votes
    root_votes: Dict[str, Counter] = defaultdict(Counter)

    # Track productions seen
    prods_seen: Counter = Counter()
    expanded_from_seen: Counter = Counter()

    for p in placements:
        if not isinstance(p, dict):
            continue
        tag = norm(p.get("tag") or p.get("context_path", "").split(".")[-1])
        if not tag:
            continue

        src_prod = p.get("source_production")
        exp_from = p.get("expanded_from")

        if src_prod:
            prods_seen[norm(src_prod)] += 1
        if exp_from:
            expanded_from_seen[norm(exp_from)] += 1

        # Root mapping heuristic:
        # If context_path is exactly a record_root tag (HEAD/INDI/FAM/...) and it has source_production, vote it in.
        cp = norm(p.get("context_path", ""))
        record_root = norm(p.get("record_root", "")) if p.get("record_root") else ""
        if cp and "." not in cp and src_prod:
            root_votes[cp].update([norm(src_prod)])
        if record_root and cp == record_root and src_prod:
            root_votes[record_root].update([norm(src_prod)])

        # Edge inference requires both expanded_from and source_production
        if exp_from and src_prod:
            parent = norm(exp_from)
            child = norm(src_prod)
            k = (parent, tag)
            edge_votes[k].update([child])

            # keep "widest" min/max (min: max of mins; max: M if any M else max int)
            mn = norm_min(p.get("min", 0))
            mx = norm_max(p.get("max", "M"))

            if k not in edge_min:
                edge_min[k] = mn
            else:
                edge_min[k] = max(edge_min[k], mn)

            if k not in edge_max:
                edge_max[k] = mx
            else:
                a = edge_max[k]
                b = mx
                if a == "M" or b == "M":
                    edge_max[k] = "M"
                else:
                    try:
                        edge_max[k] = str(max(int(a), int(b)))
                    except Exception:
                        edge_max[k] = "M"

    # Choose root map
    root_tag_map: Dict[str, str] = {}
    for r, c in root_votes.items():
        prod, _ = c.most_common(1)[0]
        root_tag_map[r] = prod

    # If we didn't see TRLR, force TRLR->TRLR as a terminal "production"
    if "TRLR" not in root_tag_map:
        root_tag_map["TRLR"] = "TRLR"

    record_roots = sorted(root_tag_map.keys())

    # Build productions table
    productions: Dict[str, Dict[str, Any]] = {}
    all_parent_prods = sorted({k[0] for k in edge_votes.keys()} | set(root_tag_map.values()))

    for parent in all_parent_prods:
        productions[parent] = {"children": []}

    # materialize edges
    for (parent, tag), votes in edge_votes.items():
        child, _ = votes.most_common(1)[0]
        productions.setdefault(parent, {"children": []})
        productions[parent]["children"].append({
            "tag": tag,
            "min": edge_min.get((parent, tag), 0),
            "max": edge_max.get((parent, tag), "M"),
            "level_delta": 1,
            "child_production": child,
            "votes": dict(votes),
        })

    # Sort children for determinism
    for parent in productions:
        productions[parent]["children"].sort(key=lambda x: (x["tag"], x.get("child_production") or ""))

    meta = {
        "generated_at": (datetime.utcnow().isoformat(timespec="seconds") + "Z") if not args.no_timestamp else None,
        "source": str(args.canonical_placements),
        "stats": {
            "placements_in": len(placements),
            "productions_out": len(productions),
            "edges_out": sum(len(productions[p]["children"]) for p in productions),
            "record_roots": len(record_roots),
        },
    }

    out = {
        "meta": meta,
        "record_roots": record_roots,
        "root_tag_map": root_tag_map,
        "productions": productions,
    }

    write_json(args.out, out)

    args.report_dir.mkdir(parents=True, exist_ok=True)
    # small report: how many edges have child_production non-null?
    nonnull = 0
    total = 0
    for p in productions.values():
        for ch in p.get("children", []):
            total += 1
            if ch.get("child_production"):
                nonnull += 1

    report = {
        "meta": meta,
        "edge_child_production_nonnull": nonnull,
        "edge_total": total,
        "nonnull_ratio": (nonnull / total) if total else 0.0,
        "record_roots": record_roots,
        "root_tag_map": root_tag_map,
    }
    write_json(args.report_dir / "inferred_graph_report.json", report)

    print(f"Wrote inferred production graph: {args.out}")
    print(f"Productions: {meta['stats']['productions_out']}")
    print(f"Edges: {meta['stats']['edges_out']} (nonnull child_production ratio: {report['nonnull_ratio']:.3f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
