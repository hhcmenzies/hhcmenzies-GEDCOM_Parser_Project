#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any, Dict, Set
from collections import Counter

def norm(x: Any) -> str:
    return str(x).strip().upper()

def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def extract_tag_set_from_structured(records: list[dict]) -> Counter:
    counter = Counter()
    for rec in records:
        tag = norm(rec.get("tag", ""))
        if tag:
            counter[tag] += 1
    return counter

def extract_standard_tags(tag_dict: dict) -> Set[str]:
    # Accept both {"tags": {...}} or flat {...}
    tags = tag_dict.get("tags") if "tags" in tag_dict else tag_dict
    return {norm(t) for t in tags}

def main():
    ap = argparse.ArgumentParser(description="Analyze structured GEDCOM tags by standard vs custom")
    ap.add_argument("--structured", required=True, type=Path)
    ap.add_argument("--canonical", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    structured = read_json(args.structured)
    tag_counter = extract_tag_set_from_structured(structured)
    tag_dict = read_json(args.canonical)
    standard_tags = extract_standard_tags(tag_dict)

    standard = {}
    custom = {}

    for tag, count in tag_counter.items():
        (standard if tag in standard_tags else custom)[tag] = count

    report = {
        "total_tags": len(tag_counter),
        "standard_tags": dict(sorted(standard.items())),
        "custom_tags": dict(sorted(custom.items())),
        "summary": {
            "standard_tag_count": len(standard),
            "custom_tag_count": len(custom),
            "standard_total_lines": sum(standard.values()),
            "custom_total_lines": sum(custom.values())
        }
    }

    with args.out.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"Wrote tag classification report: {args.out}")

if __name__ == "__main__":
    main()
