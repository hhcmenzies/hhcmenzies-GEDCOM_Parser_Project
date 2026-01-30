#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
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


def last_seg(dotpath: str) -> str:
    dotpath = norm(dotpath)
    return dotpath.split(".")[-1] if dotpath else ""


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Infer a production graph from canonical placements (uses expanded_from + source_production)."
    )
    ap.add_argument("--placements", required=True, type=Path,
                    help="canonical_grammar_placements_gedcom551.json")
    ap.add_argument("--out", required=True, type=Path,
                    help="Output production graph JSON")
    ap.add_argument("--report-dir", required=True, type=Path)
    ap.add_argument("--no-timestamp", action="store_true")
    args = ap.parse_args()

    raw = read_json(args.placements)
    if not (isinstance(raw, dict) and isinstance(raw.get("placements"), list)):
        raise SystemExit(f"Unsupported placements JSON shape: {args.placements}")

    placements: List[Dict[str, Any]] = raw["placements"]

    # 1) Infer record_roots and root->starting_production mapping.
    # Heuristic: for a given record_root R, the immediate children of R (parent_path == R)
    # have source_production == the "record production" (e.g., INDI -> INDIVIDUAL_RECORD).
    root_prod_votes: Dict[str, Counter] = defaultdict(Counter)
    record_roots = set()

    for p in placements:
        rr = norm(p.get("record_root", ""))
        if rr:
            record_roots.add(rr)
        parent_path = norm(p.get("parent_path", ""))
        src_prod = norm(p.get("source_production", ""))
        if rr and parent_path == rr and src_prod:
            root_prod_votes[rr][src_prod] += 1

    root_tag_map: Dict[str, str] = {r: r for r in sorted(record_roots) if r}

    root_production_map: Dict[str, str] = {}
    for rr, votes in root_prod_votes.items():
        if votes:
            root_production_map[rr] = votes.most_common(1)[0][0]

    # Fallbacks for common roots (only used if not inferred)
    fallback = {
        "HEAD": "HEADER",
        "TRLR": "TRAILER",
        "INDI": "INDIVIDUAL_RECORD",
        "FAM": "FAM_RECORD",
        "SOUR": "SOURCE_RECORD",
        "REPO": "REPOSITORY_RECORD",
        "SUBM": "SUBMITTER_RECORD",
        "SUBN": "SUBMISSION_RECORD",
        "NOTE": "NOTE_RECORD",
        "OBJE": "MULTIMEDIA_RECORD",
    }
    for rr, prod in fallback.items():
        if rr in record_roots and rr not in root_production_map:
            root_production_map[rr] = prod

    # 2) Infer structure-expansion edges:
    # If a placement has expanded_from=P and source_production=C, and parent_path ends with tag T,
    # then tag T in production P expands into production C.
    expansion_votes: Dict[Tuple[str, str], Counter] = defaultdict(Counter)

    for p in placements:
        expanded_from = p.get("expanded_from")
        src_prod = p.get("source_production")
        parent_path = p.get("parent_path")

        if expanded_from is None or parent_path is None:
            continue

        P = norm(expanded_from)
        C = norm(src_prod)
        if not P or not C or P == C:
            continue

        T = last_seg(parent_path)  # the tag that triggers the expansion
        if not T:
            continue

        expansion_votes[(P, T)][C] += 1

    # Resolve expansions deterministically (most common wins; tie-break by alpha)
    expansion_map: Dict[Tuple[str, str], str] = {}
    for key, votes in expansion_votes.items():
        if not votes:
            continue
        max_count = max(votes.values())
        winners = sorted([c for c, n in votes.items() if n == max_count])
        expansion_map[key] = winners[0]

    # 3) Build production->children from placements:
    # We attach each tag to its *own* source_production (container).
    prod_children: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)

    for p in placements:
        tag = norm(p.get("tag", ""))
        src_prod = norm(p.get("source_production", ""))
        if not tag or not src_prod:
            continue

        # min/max if present
        mn = p.get("min", 0)
        mx = p.get("max", "M")

        # normalize min/max
        try:
            mn_i = int(mn)
        except Exception:
            mn_i = 0
        mx_s = str(mx)

        # if we have multiple occurrences of same tag under same production, keep "widest" bounds
        existing = prod_children[src_prod].get(tag)
        if existing is None:
            prod_children[src_prod][tag] = {
                "tag": tag,
                "min": mn_i,
                "max": mx_s,
                "level_delta": 1,
                "child_production": None,
            }
        else:
            existing["min"] = min(existing.get("min", 0), mn_i)
            # max handling: if any M => M; else max numeric
            emax = str(existing.get("max", "M"))
            if emax == "M" or mx_s == "M":
                existing["max"] = "M"
            else:
                try:
                    existing["max"] = str(max(int(emax), int(mx_s)))
                except Exception:
                    existing["max"] = "M"

    # 4) Apply inferred expansion_map onto the *parent* production’s tag entry.
    for (P, T), C in expansion_map.items():
        if P not in prod_children:
            continue
        if T not in prod_children[P]:
            # If the tag wasn't seen as a direct child of P in placements, create it anyway.
            prod_children[P][T] = {
                "tag": T,
                "min": 0,
                "max": "M",
                "level_delta": 1,
                "child_production": C,
            }
        else:
            prod_children[P][T]["child_production"] = C

    productions: Dict[str, Dict[str, Any]] = {}
    for prod, tags in prod_children.items():
        children = sorted(tags.values(), key=lambda x: x["tag"])
        productions[prod] = {"children": children}

    # Reporting
    args.report_dir.mkdir(parents=True, exist_ok=True)

    edges_rows: List[Tuple[str, str, str, int]] = []
    for (P, T), votes in expansion_votes.items():
        for C, n in votes.items():
            edges_rows.append((P, T, C, n))
    edges_rows.sort()

    with (args.report_dir / "inferred_graph_edges.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["expanded_from_production", "via_tag", "child_production", "votes"])
        for row in edges_rows:
            w.writerow(list(row))

    report = {
        "generated_at": (datetime.utcnow().isoformat(timespec="seconds") + "Z") if not args.no_timestamp else None,
        "inputs": {"placements": str(args.placements)},
        "stats": {
            "placements_in": len(placements),
            "record_roots": len(record_roots),
            "productions_out": len(productions),
            "expansion_edges_out": len(expansion_map),
        },
        "root_production_map": dict(sorted(root_production_map.items())),
    }
    write_json(args.report_dir / "inferred_graph_report.json", report)

    out = {
        "meta": {
            "source": "inferred_from_canonical_placements",
            "generated_at": report["generated_at"],
        },
        "record_roots": sorted(record_roots),
        "root_tag_map": root_tag_map,
        "root_production_map": root_production_map,
        "productions": productions,
    }
    write_json(args.out, out)

    print(f"Wrote inferred graph: {args.out}")
    print(f"Productions: {len(productions)}")
    print(f"Expansion edges: {len(expansion_map)}")
    print(f"Wrote report: {args.report_dir/'inferred_graph_report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
