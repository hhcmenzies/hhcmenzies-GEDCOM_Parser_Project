#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


def norm(x: Any) -> str:
    return str(x).strip().upper()


def main() -> int:
    ap = argparse.ArgumentParser(description="Summarize unknown_tags.jsonl (counts, roots, examples).")
    ap.add_argument("--unknown-jsonl", required=True, type=Path)
    ap.add_argument("--out-report", required=True, type=Path)
    ap.add_argument("--max-examples", type=int, default=5)
    args = ap.parse_args()

    tag_counts = Counter()
    root_counts = Counter()
    examples = {}  # tag -> list[dict]

    with args.unknown_jsonl.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            o = json.loads(line)
            t = norm(o.get("tag_u") or o.get("tag"))
            r = norm(o.get("record_root"))
            tag_counts[t] += 1
            if r:
                root_counts[r] += 1
            if t and len(examples.get(t, [])) < args.max_examples:
                examples.setdefault(t, []).append(
                    {
                        "line_no": o.get("line_no"),
                        "raw": o.get("raw"),
                        "record_root": o.get("record_root"),
                        "reason": o.get("reason"),
                    }
                )

    report = {
        "stats": {
            "unknown_tag_lines": int(sum(tag_counts.values())),
            "unknown_unique_tags": len(tag_counts),
        },
        "top": {
            "unknown_tags_top50": tag_counts.most_common(50),
            "record_roots_top30": root_counts.most_common(30),
        },
        "examples_by_tag": {k: examples[k] for k, _ in tag_counts.most_common(50)},
    }

    args.out_report.parent.mkdir(parents=True, exist_ok=True)
    with args.out_report.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, sort_keys=True)

    print(f"Wrote: {args.out_report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
