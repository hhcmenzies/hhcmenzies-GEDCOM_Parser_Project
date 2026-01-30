#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


def read_json(p: Path) -> Any:
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(p: Path, obj: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=True)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Draft production graph from gedcom55_structures.json (structure->children edges)."
    )
    ap.add_argument("--structures", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    s = read_json(args.structures)
    productions: Dict[str, Dict[str, Any]] = {}

    for key, body in s.items():
        if not isinstance(body, dict):
            continue

        children = body.get("children", {})
        out_children: List[Dict[str, Any]] = []

        # children can be dict (tag->meta) or list; normalize both
        if isinstance(children, dict):
            items = list(children.items())
        elif isinstance(children, list):
            items = []
            for c in children:
                if isinstance(c, str):
                    items.append((c, {}))
                elif isinstance(c, dict):
                    tag = c.get("tag") or c.get("name") or c.get("key")
                    items.append((tag, c))
        else:
            items = []

        for tag, meta in items:
            if not tag:
                continue
            tag = str(tag).strip().upper()
            m = meta if isinstance(meta, dict) else {}
            out_children.append(
                {
                    "tag": tag,
                    "min": int(m.get("min", 0)) if str(m.get("min", "")).isdigit() else 0,
                    "max": str(m.get("max", "M")),
                    "child_production": None,
                    "level_delta": 1,
                }
            )

        out_children.sort(key=lambda x: x["tag"])
        productions[str(key).strip().upper()] = {"children": out_children}

    record_roots = ["HEAD", "TRLR", "INDI", "FAM", "SOUR", "REPO", "SUBM", "SUBN", "NOTE", "OBJE"]

    out = {
        "meta": {"source": "gedcom55_structures.json_draft_graph"},
        "record_roots": record_roots,
        "root_tag_map": {r: r for r in record_roots},
        "productions": productions,
    }
    write_json(args.out, out)

    print(f"Wrote draft production graph: {args.out}")
    print(f"Productions: {len(productions)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
