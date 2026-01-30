#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple


def norm(x: Any) -> str:
    return str(x).strip().upper()

def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)

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

def write_json(p: Path, obj: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=True)

def main() -> int:
    ap = argparse.ArgumentParser(description="Build vendor-extension grammar from unknown_tags.jsonl with parent/context paths.")
    ap.add_argument("--raw-lines", required=True, type=Path)
    ap.add_argument("--unknown-tags", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--max-examples", type=int, default=8)
    args = ap.parse_args()

    system_id = read_head_sour_from_raw_lines(args.raw_lines)
    system_id_s = sanitize_filename(system_id)

    tag_counts = Counter()
    root_counts = Counter()
    parent_pair_counts = Counter()    # (parent_tag, tag)
    context_counts = Counter()        # context_path
    examples_by_tag: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    examples_by_pair: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for o in iter_jsonl(args.unknown_tags):
        t = norm(o.get("tag_u") or o.get("tag"))
        r = norm(o.get("record_root"))
        pt = norm(o.get("parent_tag")) if o.get("parent_tag") else ""
        cp = norm(o.get("context_path")) if o.get("context_path") else ""

        if not t:
            continue

        tag_counts[t] += 1
        if r:
            root_counts[r] += 1
        if pt:
            parent_pair_counts[(pt, t)] += 1
        if cp:
            context_counts[cp] += 1

        if len(examples_by_tag[t]) < args.max_examples:
            examples_by_tag[t].append(
                {
                    "line_no": o.get("line_no"),
                    "raw": o.get("raw"),
                    "record_root": o.get("record_root"),
                    "parent_tag": o.get("parent_tag"),
                    "context_path": o.get("context_path"),
                }
            )

        if pt:
            key = f"{pt}->{t}"
            if len(examples_by_pair[key]) < args.max_examples:
                examples_by_pair[key].append(
                    {
                        "line_no": o.get("line_no"),
                        "raw": o.get("raw"),
                        "record_root": o.get("record_root"),
                        "context_path": o.get("context_path"),
                    }
                )

    out = {
        "meta": {
            "system_id": system_id,
            "system_id_sanitized": system_id_s,
            "source_unknown_tags": str(args.unknown_tags),
            "source_raw_lines": str(args.raw_lines),
            "note": "Vendor/user-defined tags are usually underscore-prefixed; meaning is vendor/system-specific (see HEAD.SOUR).",
        },
        "stats": {
            "unknown_unique_tags": int(len(tag_counts)),
            "unknown_total_lines": int(sum(tag_counts.values())),
            "record_roots_seen": dict(root_counts),
            "unique_parent_pairs": int(len(parent_pair_counts)),
            "unique_context_paths": int(len(context_counts)),
        },
        "top": {
            "unknown_tags_top30": tag_counts.most_common(30),
            "parent_pairs_top30": [([a, b], c) for (a, b), c in parent_pair_counts.most_common(30)],
            "context_paths_top30": context_counts.most_common(30),
        },
        "tags": {
            t: {
                "count": int(tag_counts[t]),
                "examples": examples_by_tag[t],
            }
            for t in sorted(tag_counts)
        },
        "parent_pairs": {
            f"{a}->{b}": {
                "count": int(c),
                "examples": examples_by_pair.get(f"{a}->{b}", []),
            }
            for (a, b), c in parent_pair_counts.items()
        },
    }

    write_json(args.out, out)
    print(f"Wrote: {args.out} (system_id={system_id!r}, tags={len(tag_counts)}, lines={sum(tag_counts.values())})")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
