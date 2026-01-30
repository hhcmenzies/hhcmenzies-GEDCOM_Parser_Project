#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, Optional, Tuple

LINE_RE = re.compile(
    r"^\s*(?P<level>\d+)\s+"
    r"(?:(?P<xref>@[^@]+@)\s+)?"
    r"(?P<tag>[A-Za-z0-9_]+)"
    r"(?:\s+(?P<rest>.*?))?\s*$"
)

@dataclass(frozen=True)
class ParsedLine:
    line_no: int
    raw: str
    level: Optional[int]
    xref: Optional[str]
    tag: Optional[str]
    value: str

def norm(x: Any) -> str:
    return str(x).strip().upper()

def read_json(p: Path) -> Any:
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)

def load_canonical_tag_set(path: Path) -> set[str]:
    """
    Accepts either:
      - {"tags": { "INDI": {...}, ... }}
      - { "INDI": {...}, ... }
    """
    raw = read_json(path)
    if isinstance(raw, dict) and "tags" in raw and isinstance(raw["tags"], dict):
        d = raw["tags"]
    elif isinstance(raw, dict):
        d = raw
    else:
        d = {}
    return {norm(k) for k in d.keys()}

def parse_line(line_no: int, raw: str) -> ParsedLine:
    m = LINE_RE.match(raw.rstrip("\n"))
    if not m:
        return ParsedLine(line_no=line_no, raw=raw.rstrip("\n"), level=None, xref=None, tag=None, value="")
    lvl = int(m.group("level"))
    xref = m.group("xref")
    tag = m.group("tag")
    rest = m.group("rest") or ""
    return ParsedLine(line_no=line_no, raw=raw.rstrip("\n"), level=lvl, xref=xref, tag=tag, value=rest)

def iter_lines(ged_path: Path) -> Iterator[ParsedLine]:
    with ged_path.open("r", encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f, start=1):
            yield parse_line(i, line)

def main() -> int:
    ap = argparse.ArgumentParser(description="Capture GEDCOM raw lines as JSONL + unknown tags report (with parent/context).")
    ap.add_argument("--ged", required=True, type=Path)
    ap.add_argument("--canonical-tags", required=True, type=Path)
    ap.add_argument("--out-dir", required=True, type=Path)
    ap.add_argument("--treat-underscore-as-known", action="store_true",
                    help="If set, tags starting with '_' are NOT treated as unknown.")
    args = ap.parse_args()

    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    canonical = load_canonical_tag_set(args.canonical_tags)

    raw_lines_path = out_dir / "raw_lines.jsonl"
    unknown_path = out_dir / "unknown_tags.jsonl"
    report_path = out_dir / "raw_capture_report.json"

    # stack holds the currently-open contexts by level:
    # (level, tag_u, context_path, record_root)
    stack: list[Tuple[int, str, str, str]] = []
    current_record_root = "UNKNOWN"

    parse_failures = 0
    total_lines = 0

    tag_counts = Counter()
    unknown_counts = Counter()
    unique_tags = set()

    # Also track parent-child and contexts (helps later)
    parent_child_counts = Counter()  # (parent_tag, tag)
    context_counts = Counter()
    record_root_counts = Counter()

    with raw_lines_path.open("w", encoding="utf-8") as raw_out, unknown_path.open("w", encoding="utf-8") as unk_out:
        for pl in iter_lines(args.ged):
            total_lines += 1

            if pl.level is None or pl.tag is None:
                parse_failures += 1
                o = {
                    "line_no": pl.line_no,
                    "raw": pl.raw,
                    "level": None,
                    "xref": None,
                    "tag": None,
                    "tag_u": None,
                    "value": "",
                    "record_root": current_record_root,
                    "parent_tag": None,
                    "parent_path": None,
                    "context_path": None,
                    "reason": "PARSE_FAILURE",
                }
                raw_out.write(json.dumps(o, ensure_ascii=False) + "\n")
                continue

            lvl = int(pl.level)
            tag_u = norm(pl.tag)
            val = pl.value or ""
            unique_tags.add(tag_u)
            tag_counts[tag_u] += 1

            # unwind stack to parent level
            while stack and stack[-1][0] >= lvl:
                stack.pop()

            # record_root resets at level 0
            if lvl == 0:
                current_record_root = tag_u
                # start context path at root tag
                context_path = tag_u
                parent_tag = None
                parent_path = None
                stack.append((lvl, tag_u, context_path, current_record_root))
            else:
                if stack:
                    parent_tag = stack[-1][1]
                    parent_path = stack[-1][2]
                    record_root = stack[-1][3]
                else:
                    parent_tag = None
                    parent_path = None
                    record_root = current_record_root

                # create context path
                if parent_path:
                    context_path = f"{parent_path}.{tag_u}"
                else:
                    context_path = tag_u

                stack.append((lvl, tag_u, context_path, record_root))
                current_record_root = record_root

            record_root_counts[current_record_root] += 1
            context_counts[context_path] += 1
            if parent_tag:
                parent_child_counts[(parent_tag, tag_u)] += 1

            o = {
                "line_no": pl.line_no,
                "raw": pl.raw,
                "level": lvl,
                "xref": pl.xref,
                "tag": pl.tag,
                "tag_u": tag_u,
                "value": val,
                "record_root": current_record_root,
                "parent_tag": parent_tag,
                "parent_path": parent_path,
                "context_path": context_path,
            }
            raw_out.write(json.dumps(o, ensure_ascii=False) + "\n")

            is_unknown = False
            if tag_u not in canonical:
                if args.treat_underscore_as_known and tag_u.startswith("_"):
                    is_unknown = False
                else:
                    is_unknown = True

            if is_unknown:
                unknown_counts[tag_u] += 1
                u = dict(o)
                u["reason"] = "TAG_NOT_IN_CANONICAL_TAG_DICTIONARY"
                unk_out.write(json.dumps(u, ensure_ascii=False) + "\n")

    report = {
        "inputs": {
            "ged": str(args.ged),
            "canonical_tags": str(args.canonical_tags),
            "treat_underscore_as_known": bool(args.treat_underscore_as_known),
        },
        "outputs": {
            "raw_lines_jsonl": str(raw_lines_path),
            "unknown_tags_jsonl": str(unknown_path),
            "report_json": str(report_path),
        },
        "stats": {
            "lines_total": total_lines,
            "parse_failures": parse_failures,
            "unique_tags_total": len(unique_tags),
            "unknown_unique_tags": len(unknown_counts),
            "unknown_tag_lines": int(sum(unknown_counts.values())),
        },
        "top": {
            "tags_top30": tag_counts.most_common(30),
            "unknown_tags_top30": unknown_counts.most_common(30),
            "record_roots_top30": record_root_counts.most_common(30),
            "parent_child_top30": [([a, b], c) for (a, b), c in parent_child_counts.most_common(30)],
            "context_paths_top30": context_counts.most_common(30),
        },
    }

    with report_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, sort_keys=True)

    print(f"Wrote raw lines:     {raw_lines_path} (lines={total_lines})")
    print(f"Wrote unknown tags:  {unknown_path} (lines={sum(unknown_counts.values())}, unique={len(unknown_counts)})")
    print(f"Wrote report:        {report_path}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
