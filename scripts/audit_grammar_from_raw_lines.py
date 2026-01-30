#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Tuple, Set


def norm(x: Any) -> str:
    return str(x).strip().upper()


def read_json(p: Path) -> Any:
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_backbone_paths(backbone_file: Path) -> Set[str]:
    raw = read_json(backbone_file)
    pl = raw["placements"] if isinstance(raw, dict) and "placements" in raw else raw
    out: Set[str] = set()
    for p in pl:
        if isinstance(p, dict) and "context_path" in p:
            out.add(norm(p["context_path"]))
        elif isinstance(p, str):
            out.add(norm(p))
    return out


def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Audit observed GEDCOM grammar (context paths + stack anomalies) from raw_lines.jsonl."
    )
    ap.add_argument("--raw-lines", required=True, type=Path)
    ap.add_argument("--backbone", required=True, type=Path)
    ap.add_argument("--out-report", required=True, type=Path)
    ap.add_argument("--out-missing-paths", required=True, type=Path)
    ap.add_argument("--max-lines", type=int, default=0, help="0 = no limit")
    args = ap.parse_args()

    backbone_paths = load_backbone_paths(args.backbone)

    # Stack holds tuples: (level, tag, context_path)
    stack: List[Tuple[int, str, str]] = []

    observed_paths = Counter()
    tag_counts = Counter()
    parent_child = Counter()  # (parent_tag, child_tag)
    record_roots = Counter()
    value_pointers = Counter()
    anomalies = Counter()
    missing_from_backbone = Counter()

    def current_root_tag() -> str:
        for lvl, tag, cp in reversed(stack):
            if lvl == 0:
                return tag
        return ""

    lines_total = 0
    for obj in iter_jsonl(args.raw_lines):
        lines_total += 1
        if args.max_lines and lines_total > args.max_lines:
            break

        lvl = obj.get("level", None)
        tag = obj.get("tag", None)
        val = obj.get("value", "")

        if lvl is None or tag is None:
            anomalies["missing_level_or_tag"] += 1
            continue

        lvl = int(lvl)
        tag_u = norm(tag)
        tag_counts[tag_u] += 1

        v = str(val).strip()
        if len(v) >= 3 and v.startswith("@") and v.endswith("@"):
            value_pointers[tag_u] += 1

        # --- compute cp and update stack ---
        if not stack:
            if lvl != 0:
                anomalies["first_line_not_level0"] += 1
            # IMPORTANT: define cp here (this was the bug)
            cp = tag_u
            stack = [(lvl, tag_u, cp)]
            if lvl == 0:
                record_roots[tag_u] += 1
        else:
            top_lvl = stack[-1][0]

            # Pop until parent level < current level
            if lvl <= top_lvl:
                while stack and stack[-1][0] >= lvl:
                    stack.pop()

            if stack:
                parent_lvl = stack[-1][0]
                if lvl > parent_lvl + 1:
                    anomalies["level_jump_gt_1"] += 1
            else:
                if lvl != 0:
                    anomalies["stack_emptied_nonzero_level"] += 1

            if lvl == 0:
                cp = tag_u
                stack.append((lvl, tag_u, cp))
                record_roots[tag_u] += 1
            else:
                if stack:
                    parent_lvl, parent_tag, parent_cp = stack[-1]
                    cp = parent_cp + "." + tag_u
                    parent_child[(parent_tag, tag_u)] += 1
                else:
                    cp = tag_u
                    anomalies["orphan_nonzero_level"] += 1
                stack.append((lvl, tag_u, cp))

        # --- record observations ---
        observed_paths[cp] += 1
        if cp not in backbone_paths:
            missing_from_backbone[cp] += 1

    args.out_missing_paths.parent.mkdir(parents=True, exist_ok=True)
    with args.out_missing_paths.open("w", encoding="utf-8") as f:
        for cp, cnt in missing_from_backbone.most_common():
            f.write(json.dumps({"context_path": cp, "count": cnt}, ensure_ascii=False) + "\n")

    report = {
        "inputs": {
            "raw_lines": str(args.raw_lines),
            "backbone": str(args.backbone),
        },
        "stats": {
            "lines_processed": lines_total,
            "unique_tags": len(tag_counts),
            "unique_observed_paths": len(observed_paths),
            "missing_paths_unique": len(missing_from_backbone),
            "missing_paths_total_hits": int(sum(missing_from_backbone.values())),
        },
        "anomalies": dict(anomalies),
        "top": {
            "record_roots_top20": record_roots.most_common(20),
            "tags_top30": tag_counts.most_common(30),
            "missing_paths_top50": missing_from_backbone.most_common(50),
            "parent_child_top50": [([a, b], c) for (a, b), c in parent_child.most_common(50)],
            "pointer_values_top30": value_pointers.most_common(30),
        },
    }

    args.out_report.parent.mkdir(parents=True, exist_ok=True)
    with args.out_report.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, sort_keys=True)

    print(f"Wrote report: {args.out_report}")
    print(f"Wrote missing paths JSONL: {args.out_missing_paths} (unique={len(missing_from_backbone)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
