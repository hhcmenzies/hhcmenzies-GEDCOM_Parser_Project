#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

LINE_RE = re.compile(r'^(?P<lvl>\d+)\s+(?:(?P<xref>@[^@]+@)\s+)?(?P<tag>[^\s]+)(?:\s+(?P<val>.*))?$')

def read_text_guess(path: Path) -> str:
    for enc in ("utf-8-sig","utf-8","utf-16","utf-16le","utf-16be","latin-1"):
        try:
            return path.read_text(encoding=enc, errors="strict")
        except Exception:
            continue
    return path.read_text(encoding="utf-8", errors="replace")

def iter_ged_files(root: Path) -> list[Path]:
    if root.is_file() and root.suffix.lower()==".ged":
        return [root]
    return sorted([p for p in root.rglob("*") if p.is_file() and p.suffix.lower()==".ged"])

def parse_paths(text: str) -> Tuple[Counter, Counter]:
    stack: list[str] = []
    tag_counts: Counter = Counter()
    path_counts: Counter = Counter()

    for raw in text.splitlines():
        line = raw.rstrip("\r\n")
        if not line.strip():
            continue
        m = LINE_RE.match(line)
        if not m:
            continue
        lvl = int(m.group("lvl"))
        tag_u = m.group("tag").strip().upper()
        tag_counts[tag_u] += 1

        while len(stack) > lvl:
            stack.pop()

        if lvl == 0:
            stack = [tag_u]
            path = tag_u
        else:
            if not stack:
                stack = ["_NO_ROOT_"]
            while len(stack) < lvl:
                stack.append("_MISSING_")
            if len(stack) == lvl:
                stack.append(tag_u)
            else:
                stack[lvl] = tag_u
            path = ".".join(stack[:lvl] + [tag_u])

        path_counts[path] += 1

    return tag_counts, path_counts

def load_canonical_paths(path: Optional[Path]) -> set[str]:
    if not path:
        return set()
    raw = json.load(open(path,"r",encoding="utf-8"))
    placements = raw.get("placements") if isinstance(raw,dict) and "placements" in raw else raw
    out=set()
    if isinstance(placements,list):
        for it in placements:
            if isinstance(it,dict) and isinstance(it.get("context_path"),str):
                out.add(it["context_path"].strip().upper())
    return out

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--report-dir", required=True, type=Path)
    ap.add_argument("--canonical-grammar", type=Path, default=None)
    ap.add_argument("--no-timestamp", action="store_true")
    args=ap.parse_args()

    files=iter_ged_files(args.inp)
    if not files:
        raise SystemExit(f"No .ged files found under: {args.inp}")

    all_tags=Counter()
    all_paths=Counter()
    per_file=[]

    for f in files:
        txt=read_text_guess(f)
        tc, pc = parse_paths(txt)
        all_tags.update(tc)
        all_paths.update(pc)
        per_file.append({"file": str(f), "tags_distinct": len(tc), "paths_distinct": len(pc), "lines": len(txt.splitlines())})

    observed_paths=sorted(all_paths.keys())
    observed_tags=sorted(all_tags.keys())
    extension_tags=sorted([t for t in observed_tags if t.startswith("_")])

    canonical_paths=load_canonical_paths(args.canonical_grammar)

    observed_set=set(p.upper() for p in observed_paths)
    gaps={
        "canonical_paths_missing_in_observed": sorted(canonical_paths - observed_set) if canonical_paths else [],
        "observed_paths_missing_in_canonical": sorted(observed_set - canonical_paths) if canonical_paths else [],
    }

    summary={
        "_meta":{
            "generated_at": (datetime.utcnow().isoformat(timespec="seconds")+"Z") if not args.no_timestamp else None,
            "input": str(args.inp),
            "files_count": len(files),
        },
        "counts":{
            "distinct_tags": len(observed_tags),
            "distinct_paths": len(observed_paths),
            "distinct_extension_tags": len(extension_tags),
        },
        "extensions": extension_tags,
        "per_file": per_file,
        "observed_tags_top": all_tags.most_common(50),
        "observed_paths_top": all_paths.most_common(50),
        "gaps_vs_canonical":{
            "observed_paths_missing_in_canonical_count": len(gaps["observed_paths_missing_in_canonical"]),
            "canonical_paths_missing_in_observed_count": len(gaps["canonical_paths_missing_in_observed"]),
        }
    }

    out_obj={"summary": summary, "observed": {"paths": observed_paths, "tags": observed_tags}, "gaps": gaps}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    json.dump(out_obj, open(args.out,"w",encoding="utf-8"), ensure_ascii=False, indent=2, sort_keys=True)

    args.report_dir.mkdir(parents=True, exist_ok=True)
    json.dump(summary, open(args.report_dir/"observed_gaps_vs_canonical.json","w",encoding="utf-8"), ensure_ascii=False, indent=2, sort_keys=True)

    with open(args.report_dir/"observed_gaps_vs_canonical.csv","w",encoding="utf-8",newline="") as f:
        w=csv.writer(f)
        w.writerow(["type","value"])
        for pth in gaps["observed_paths_missing_in_canonical"]:
            w.writerow(["observed_path_missing_in_canonical", pth])
        for t in extension_tags:
            w.writerow(["extension_tag", t])

    md=[]
    md.append("# Observed Universe Summary\n")
    md.append(f"- Files scanned: **{len(files)}**")
    md.append(f"- Distinct tags: **{len(observed_tags)}**")
    md.append(f"- Distinct paths: **{len(observed_paths)}**")
    md.append(f"- Distinct extension tags: **{len(extension_tags)}**\n")
    if args.canonical_grammar:
        md.append("## Gaps vs canonical placements\n")
        md.append(f"- Observed paths missing in canonical: **{len(gaps['observed_paths_missing_in_canonical'])}**")
        md.append(f"- Canonical paths missing in observed: **{len(gaps['canonical_paths_missing_in_observed'])}**\n")
    md.append("## Extension tags\n")
    md.append(", ".join(extension_tags[:120]) + (" …" if len(extension_tags)>120 else ""))
    (args.report_dir/"observed_summary.md").write_text("\n".join(md), encoding="utf-8")

    print(f"Observed files: {len(files)}")
    print(f"Distinct tags: {len(observed_tags)}")
    print(f"Distinct context paths: {len(observed_paths)}")
    print(f"Distinct extension tags: {len(extension_tags)}")
    print(f"Wrote: {args.out}")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
