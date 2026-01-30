#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List


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
    """
    Attempt to find HEAD.SOUR value from raw_lines.jsonl.

    We look for:
      0 HEAD
      1 SOUR <system_id>
    """
    in_head = False
    for o in iter_jsonl(raw_lines_jsonl):
        lvl = o.get("level")
        tag = norm(o.get("tag"))
        val = (o.get("value") or "").strip()

        if lvl == 0 and tag == "HEAD":
            in_head = True
            continue

        if in_head:
            # next level-0 record ends HEAD
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
    ap = argparse.ArgumentParser(
        description="Build a vendor-extension grammar report from unknown_tags.jsonl (keyed by HEAD.SOUR where possible)."
    )
    ap.add_argument("--raw-lines", required=True, type=Path, help="outputs/.../raw_lines.jsonl (used to read HEAD.SOUR)")
    ap.add_argument("--unknown-tags", required=True, type=Path, help="outputs/.../unknown_tags.jsonl")
    ap.add_argument("--out", required=True, type=Path, help="Output JSON report")
    ap.add_argument("--max-examples", type=int, default=5)
    args = ap.parse_args()

    system_id = read_head_sour_from_raw_lines(args.raw_lines)
    system_id_sanitized = sanitize_filename(system_id)

    tag_counts = Counter()
    root_counts = Counter()
    examples: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for o in iter_jsonl(args.unknown_tags):
        t = norm(o.get("tag_u") or o.get("tag"))
        r = norm(o.get("record_root"))

        if not t:
            continue

        tag_counts[t] += 1
        if r:
            root_counts[r] += 1

        if len(examples[t]) < args.max_examples:
            examples[t].append(
                {
                    "line_no": o.get("line_no"),
                    "raw": o.get("raw"),
                    "record_root": o.get("record_root"),
                    "reason": o.get("reason"),
                }
            )

    out = {
        "meta": {
            "system_id": system_id,
            "system_id_sanitized": system_id_sanitized,
            "source_unknown_tags": str(args.unknown_tags),
            "source_raw_lines": str(args.raw_lines),
            "note": "Underscore tags are legal user-defined tags; semantics are vendor/system-specific (see HEAD.SOUR).",
        },
        "stats": {
            "unknown_unique_tags": int(len(tag_counts)),
            "unknown_total_lines": int(sum(tag_counts.values())),
            "record_roots_seen": dict(root_counts),
        },
        "tags": {
            t: {
                "count": int(tag_counts[t]),
                "examples": examples[t],
            }
            for t in sorted(tag_counts)
        },
    }

    write_json(args.out, out)
    print(f"Wrote: {args.out} (system_id={system_id!r}, tags={len(tag_counts)}, lines={sum(tag_counts.values())})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
