#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
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


def norm_path(s: str) -> str:
    return str(s).strip().upper()


def load_placements(path: Path) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    raw = read_json(path)
    if isinstance(raw, dict) and "placements" in raw:
        return raw["placements"], raw.get("meta", {})
    raise SystemExit(f"Unsupported placements JSON shape: {path}")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Build a candidate 'full canonical placements' file using existing merged placement universe."
    )
    ap.add_argument("--canonical-placements", required=True, type=Path)
    ap.add_argument("--merged-universe", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--report-dir", required=True, type=Path)
    ap.add_argument("--no-timestamp", action="store_true")
    args = ap.parse_args()

    canon_pl, _ = load_placements(args.canonical_placements)
    merged_pl, _ = load_placements(args.merged_universe)

    canon_by_path = {norm_path(p["context_path"]): p for p in canon_pl if "context_path" in p}
    merged_by_path = {norm_path(p["context_path"]): p for p in merged_pl if "context_path" in p}

    out_by_path = dict(canon_by_path)
    added: List[str] = []

    for cp, p in merged_by_path.items():
        if cp in out_by_path:
            continue
        q = dict(p)
        q["source_production"] = q.get("source_production") or "UNKNOWN"
        q["expanded_from"] = q.get("expanded_from") or "UNKNOWN"
        q["provenance"] = "CANDIDATE_FROM_MERGED_UNIVERSE"
        out_by_path[cp] = q
        added.append(cp)

    out_list = sorted(out_by_path.values(), key=lambda x: norm_path(x["context_path"]))

    meta = {
        "generated_at": (datetime.utcnow().isoformat(timespec="seconds") + "Z") if not args.no_timestamp else None,
        "build": "candidate_full_from_merged_universe",
        "inputs": {
            "canonical_placements": str(args.canonical_placements),
            "merged_universe": str(args.merged_universe),
        },
        "stats": {
            "canonical_in": len(canon_pl),
            "merged_in": len(merged_pl),
            "candidate_out": len(out_list),
            "added_from_merged": len(added),
        },
    }

    write_json(args.out, {"meta": meta, "placements": out_list})

    args.report_dir.mkdir(parents=True, exist_ok=True)
    write_json(args.report_dir / "canonical_candidate_report.json", meta)

    with open(args.report_dir / "candidate_added_paths.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["context_path"])
        for cp in sorted(added):
            w.writerow([cp])

    print(f"Wrote candidate canonical placements: {args.out}")
    print(f"Added from merged universe: {len(added)}")
    print(f"Wrote report: {args.report_dir/'canonical_candidate_report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
