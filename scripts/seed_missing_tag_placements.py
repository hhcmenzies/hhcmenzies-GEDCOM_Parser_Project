#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Set


def read_json(p: Path) -> Any:
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(p: Path, obj: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=True)


def norm(x: Any) -> str:
    return str(x).strip().upper()


def mk_place(cp: str, parent: str | None, record_root: str) -> Dict[str, Any]:
    parts = cp.split(".")
    return {
        "context_path": cp,
        "parent_path": parent,
        "tag": parts[-1],
        "record_root": record_root,
        "level": len(parts) - 1,
        "min": 0,
        "max": "M",
        "source_production": "MANUAL_SEED",
        "expanded_from": "MANUAL_SEED",
        "provenance": "SEEDED_MISSING_TAG",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Seed minimal placements for tags that have no context paths.")
    ap.add_argument("--backbone", required=True, type=Path)
    ap.add_argument("--coverage-report", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--report-dir", required=True, type=Path)
    ap.add_argument("--no-timestamp", action="store_true")
    args = ap.parse_args()

    bb = read_json(args.backbone)
    pl = bb["placements"] if isinstance(bb, dict) and "placements" in bb else bb
    meta_in = bb.get("meta", {}) if isinstance(bb, dict) else {}

    rep = read_json(args.coverage_report)
    missing = rep.get("coverage", {}).get("tags_without_any_context_path", []) or []
    missing = [norm(x) for x in missing]

    existing: Set[str] = set()
    for p in pl:
        if isinstance(p, dict) and "context_path" in p:
            existing.add(norm(p["context_path"]))

    out_pl: List[Dict[str, Any]] = [p for p in pl if isinstance(p, dict) and "context_path" in p]
    added: List[str] = []

    seeds: List[str] = []
    for t in missing:
        if t in ("MARB", "MARC", "MARL", "MARS"):
            seeds.append(f"FAM.{t}")
        elif t == "EMAI":
            seeds.append("INDI.EMAI")
            seeds.append("SUBM.EMAI")
        elif t == "FCID":
            seeds.append("INDI.FCID")
        else:
            seeds.append(f"INDI.{t}")

    for cp in seeds:
        CP = norm(cp)
        if CP in existing:
            continue
        parts = CP.split(".")
        record_root = parts[0]
        parent = ".".join(parts[:-1]) if len(parts) > 1 else None
        out_pl.append(mk_place(CP, parent, record_root))
        existing.add(CP)
        added.append(CP)

    out_meta = {
        "generated_at": (datetime.utcnow().isoformat(timespec="seconds") + "Z") if not args.no_timestamp else None,
        "build": "seed_missing_tag_placements",
        "inputs": {"backbone": str(args.backbone), "coverage_report": str(args.coverage_report)},
        "stats": {
            "placements_in": len(pl),
            "placements_out": len(out_pl),
            "missing_tags_in_report": len(missing),
            "seed_paths_added": len(added),
        },
        "backbone_meta": meta_in,
    }

    out_pl_sorted = sorted(out_pl, key=lambda x: norm(x["context_path"]))
    write_json(args.out, {"meta": out_meta, "placements": out_pl_sorted})

    args.report_dir.mkdir(parents=True, exist_ok=True)
    write_json(args.report_dir / "seed_missing_tag_placements_report.json", {"added_paths": added, "meta": out_meta})

    print(f"Wrote: {args.out} (added={len(added)} total={len(out_pl_sorted)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
