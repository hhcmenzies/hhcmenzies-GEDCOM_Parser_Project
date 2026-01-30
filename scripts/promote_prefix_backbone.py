#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


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
    ap = argparse.ArgumentParser(description="Promote prefix-graph traversal placements to canonical backbone.")
    ap.add_argument("--in", dest="inp", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--meta-source", required=True, type=str)
    ap.add_argument("--no-timestamp", action="store_true")
    args = ap.parse_args()

    raw = read_json(args.inp)
    pl = raw["placements"] if isinstance(raw, dict) and "placements" in raw else raw

    out_pl: List[Dict[str, Any]] = []
    seen = set()

    for p in pl:
        if not isinstance(p, dict) or "context_path" not in p:
            continue
        cp = norm(p["context_path"])
        if cp in seen:
            continue
        seen.add(cp)

        parts = cp.split(".")
        out_pl.append({
            "context_path": cp,
            "parent_path": ".".join(parts[:-1]) if len(parts) > 1 else None,
            "tag": parts[-1],
            "record_root": parts[0],
            "level": len(parts) - 1,
            # backbone provenance
            "provenance": "CANONICAL_BACKBONE_PREFIX_GRAPH",
        })

    out_pl.sort(key=lambda x: x["context_path"])

    meta = {
        "generated_at": (datetime.utcnow().isoformat(timespec="seconds")+"Z") if not args.no_timestamp else None,
        "build": "canonical_backbone_from_prefix_graph",
        "source": args.meta_source,
        "stats": {"placements_out": len(out_pl)},
    }

    write_json(args.out, {"meta": meta, "placements": out_pl})
    print(f"Wrote: {args.out} (placements={len(out_pl)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
