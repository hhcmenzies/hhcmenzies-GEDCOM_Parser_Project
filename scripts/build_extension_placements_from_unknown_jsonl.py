#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


def norm(x: Any) -> str:
    return str(x).strip().upper()

def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)

def write_json(p: Path, obj: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=True)

def sanitize_filename(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return "UNKNOWN_SYSTEM"
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", s)
    return s[:80] if len(s) > 80 else s

def read_head_sour_from_raw_lines(raw_lines_jsonl: Path) -> str:
    in_head = False
    for o in iter_jsonl(raw_lines_jsonl):
        lvl = o.get("level")
        tag = norm(o.get("tag"))
        val = (o.get("value") or "").strip()
        if lvl == 0 and tag == "HEAD":
            in_head = True
            continue
        if in_head:
            if lvl == 0 and tag != "HEAD":
                break
            if lvl == 1 and tag == "SOUR" and val:
                return val
    return "UNKNOWN_SYSTEM"

def mk_place(o: Dict[str, Any], system_id: str) -> Optional[Dict[str, Any]]:
    cp = norm(o.get("context_path") or "")
    if not cp:
        return None
    parent_path = o.get("parent_path")
    parent_path = norm(parent_path) if parent_path else None
    record_root = norm(o.get("record_root") or "")
    tag_u = norm(o.get("tag_u") or o.get("tag") or "")
    if not tag_u:
        return None

    # level from dotpath depth (record_root is level 0)
    level = cp.count(".")
    return {
        "context_path": cp,
        "parent_path": parent_path,
        "tag": tag_u,
        "record_root": record_root or None,
        "level": level,
        # Vendor tags: cardinality unknown -> keep permissive
        "min": 0,
        "max": "M",
        "source_production": "VENDOR_EXTENSION",
        "expanded_from": "VENDOR_EXTENSION",
        "provenance": f"VENDOR_EXTENSION:{system_id}",
    }

def main() -> int:
    ap = argparse.ArgumentParser(description="Promote unknown/vendor tag contexts (from unknown_tags.jsonl) into extension placements.")
    ap.add_argument("--raw-lines", required=True, type=Path, help="raw_lines.jsonl (used for HEAD.SOUR)")
    ap.add_argument("--unknown-tags", required=True, type=Path, help="unknown_tags.jsonl (must include context_path/parent_path)")
    ap.add_argument("--out", required=True, type=Path, help="placements.vendor.<system>.json")
    ap.add_argument("--report", required=True, type=Path)
    ap.add_argument("--max-examples", type=int, default=5)
    args = ap.parse_args()

    system_id = read_head_sour_from_raw_lines(args.raw_lines)
    system_id_s = sanitize_filename(system_id)

    # Deduplicate by context_path
    placements_by_cp: Dict[str, Dict[str, Any]] = {}
    cp_counts = Counter()
    tag_counts = Counter()
    root_counts = Counter()
    examples_by_tag: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for o in iter_jsonl(args.unknown_tags):
        cp = norm(o.get("context_path") or "")
        t = norm(o.get("tag_u") or o.get("tag") or "")
        rr = norm(o.get("record_root") or "")
        if not cp or not t:
            continue

        cp_counts[cp] += 1
        tag_counts[t] += 1
        if rr:
            root_counts[rr] += 1

        if len(examples_by_tag[t]) < args.max_examples:
            examples_by_tag[t].append(
                {
                    "line_no": o.get("line_no"),
                    "raw": o.get("raw"),
                    "record_root": o.get("record_root"),
                    "context_path": o.get("context_path"),
                    "parent_path": o.get("parent_path"),
                }
            )

        if cp not in placements_by_cp:
            pl = mk_place(o, system_id=system_id_s)
            if pl:
                placements_by_cp[cp] = pl

    placements = [placements_by_cp[k] for k in sorted(placements_by_cp.keys())]

    out_obj = {
        "meta": {
            "system_id": system_id,
            "system_id_sanitized": system_id_s,
            "source_raw_lines": str(args.raw_lines),
            "source_unknown_tags": str(args.unknown_tags),
            "note": "These are vendor/user-defined tag placements observed in a real GEDCOM export. Cardinality is permissive (0..M).",
        },
        "placements": placements,
    }

    report_obj = {
        "meta": {
            "system_id": system_id,
            "system_id_sanitized": system_id_s,
        },
        "stats": {
            "unknown_lines_in": int(sum(tag_counts.values())),
            "unknown_unique_tags": int(len(tag_counts)),
            "unique_context_paths_promoted": int(len(placements)),
            "record_roots_seen": dict(root_counts),
        },
        "top": {
            "tags_top30": tag_counts.most_common(30),
            "context_paths_top30": cp_counts.most_common(30),
        },
        "examples_by_tag": {k: examples_by_tag[k] for k in sorted(examples_by_tag.keys())},
    }

    write_json(args.out, out_obj)
    write_json(args.report, report_obj)
    print(f"Wrote placements: {args.out} (system_id={system_id!r}, contexts={len(placements)})")
    print(f"Wrote report:     {args.report} (unknown_unique_tags={len(tag_counts)})")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
