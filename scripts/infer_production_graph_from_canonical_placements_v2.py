#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple


# ---- helpers ----
def read_json(p: Path) -> Any:
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)

def write_json(p: Path, obj: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=True)

def norm(x: Any) -> str:
    return str(x).strip().upper()

def norm_min(v: Any) -> int:
    try:
        return int(str(v).strip())
    except Exception:
        return 0

def norm_max(v: Any) -> str:
    if v is None:
        return "M"
    s = str(v).strip().upper()
    if s in ("M", "N", "*", ""):
        return "M"
    try:
        int(s)
        return s
    except Exception:
        return "M"


# ---- main ----
def main() -> int:
    ap = argparse.ArgumentParser(
        description="Infer a production graph from canonical placements: expanded_from --tag--> source_production, plus robust record-root inference."
    )
    ap.add_argument("--canonical-placements", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--report-dir", required=True, type=Path)
    ap.add_argument("--no-timestamp", action="store_true")
    args = ap.parse_args()

    raw = read_json(args.canonical_placements)
    placements = raw["placements"] if isinstance(raw, dict) and "placements" in raw else raw
    if not isinstance(placements, list):
        raise SystemExit("Unsupported placements JSON shape (expected list or {placements:[...]})")

    # Edge votes: (parent_prod, tag) -> child_prod
    edge_votes: Dict[Tuple[str, str], Counter] = defaultdict(Counter)
    edge_min: Dict[Tuple[str, str], int] = {}
    edge_max: Dict[Tuple[str, str], str] = {}

    # Root votes: record_root_tag (INDI/FAM/...) -> production_name (INDIVIDUAL_RECORD/FAM_RECORD/...)
    # Inference rule: if a placement has parent_path == record_root and expanded_from exists, then record_root votes for expanded_from.
    root_votes: Dict[str, Counter] = defaultdict(Counter)

    # Always allow these record roots (GEDCOM 5.5.x)
    default_record_roots = ["HEAD","TRLR","INDI","FAM","SOUR","REPO","SUBM","SUBN","NOTE","OBJE"]

    for p in placements:
        if not isinstance(p, dict):
            continue

        cp = norm(p.get("context_path", ""))
        if not cp:
            continue

        tag = norm(p.get("tag") or cp.split(".")[-1])
        parent_path = norm(p.get("parent_path") or (".".join(cp.split(".")[:-1]) if "." in cp else "")) or None
        record_root = norm(p.get("record_root") or (cp.split(".")[0] if cp else ""))

        src_prod = p.get("source_production")
        exp_from = p.get("expanded_from")

        # ---- root inference (key fix) ----
        # If this placement is a direct child of the record root (e.g., parent_path == INDI),
        # then expanded_from is the record root's production.
        if record_root and parent_path and parent_path == record_root and exp_from:
            root_votes[record_root].update([norm(exp_from)])

        # Also: if we ever see a dotless cp that matches a root, and it has source_production, treat that as root mapping too.
        if "." not in cp and cp in default_record_roots and src_prod:
            root_votes[cp].update([norm(src_prod)])

        # ---- edge inference ----
        if exp_from and src_prod:
            parent_prod = norm(exp_from)
            child_prod = norm(src_prod)
            k = (parent_prod, tag)
            edge_votes[k].update([child_prod])

            mn = norm_min(p.get("min", 0))
            mx = norm_max(p.get("max", "M"))

            edge_min[k] = max(edge_min.get(k, 0), mn)
            prev_mx = edge_max.get(k, None)
            if prev_mx is None:
                edge_max[k] = mx
            else:
                if prev_mx == "M" or mx == "M":
                    edge_max[k] = "M"
                else:
                    try:
                        edge_max[k] = str(max(int(prev_mx), int(mx)))
                    except Exception:
                        edge_max[k] = "M"

    # Build root_tag_map, falling back to common GEDCOM mappings if canonical doesn’t vote enough.
    fallback_root_map = {
        "HEAD": "HEADER",
        "TRLR": "TRLR",
        "INDI": "INDIVIDUAL_RECORD",
        "FAM": "FAM_RECORD",
        "SOUR": "SOURCE_RECORD",
        "REPO": "REPOSITORY_RECORD",
        "SUBM": "SUBMITTER_RECORD",
        "SUBN": "SUBMISSION_RECORD",
        "NOTE": "NOTE_RECORD",
        "OBJE": "MULTIMEDIA_RECORD",
    }

    root_tag_map: Dict[str, str] = {}
    for r in default_record_roots:
        rr = norm(r)
        if rr in root_votes and root_votes[rr]:
            root_tag_map[rr] = root_votes[rr].most_common(1)[0][0]
        elif rr in fallback_root_map:
            root_tag_map[rr] = fallback_root_map[rr]

    record_roots = [r for r in default_record_roots if norm(r) in root_tag_map]

    # Build productions graph
    productions: Dict[str, Dict[str, Any]] = {}

    # Ensure all root productions exist even if no edges were inferred
    for prod in set(root_tag_map.values()):
        productions.setdefault(prod, {"children": []})

    for (parent_prod, tag), votes in edge_votes.items():
        child_prod = votes.most_common(1)[0][0]
        productions.setdefault(parent_prod, {"children": []})
        productions.setdefault(child_prod, {"children": []})
        productions[parent_prod]["children"].append({
            "tag": tag,
            "min": edge_min.get((parent_prod, tag), 0),
            "max": edge_max.get((parent_prod, tag), "M"),
            "level_delta": 1,
            "child_production": child_prod,
        })

    # Sort children deterministically
    for parent in productions:
        productions[parent]["children"].sort(key=lambda x: (x["tag"], x.get("child_production") or ""))

    # Stats
    total_edges = sum(len(productions[p]["children"]) for p in productions)
    nonnull_edges = sum(
        1 for p in productions for ch in productions[p]["children"] if ch.get("child_production")
    )
    meta = {
        "generated_at": (datetime.utcnow().isoformat(timespec="seconds") + "Z") if not args.no_timestamp else None,
        "source": str(args.canonical_placements),
        "stats": {
            "placements_in": len(placements),
            "productions_out": len(productions),
            "edges_out": total_edges,
            "record_roots": len(record_roots),
        },
    }

    out = {
        "meta": meta,
        "record_roots": [norm(r) for r in record_roots],
        "root_tag_map": {norm(k): norm(v) for k, v in root_tag_map.items()},
        "productions": productions,
    }

    write_json(args.out, out)

    args.report_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "meta": meta,
        "edge_total": total_edges,
        "edge_child_production_nonnull": nonnull_edges,
        "nonnull_ratio": (nonnull_edges / total_edges) if total_edges else 0.0,
        "record_roots": [norm(r) for r in record_roots],
        "root_tag_map": {norm(k): norm(v) for k, v in root_tag_map.items()},
    }
    write_json(args.report_dir / "inferred_graph_report.v2.json", report)

    print(f"Wrote inferred production graph: {args.out}")
    print(f"Record roots: {len(record_roots)} -> {', '.join([norm(r) for r in record_roots])}")
    print(f"Productions: {len(productions)}")
    print(f"Edges: {total_edges} (nonnull child_production ratio: {report['nonnull_ratio']:.3f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
