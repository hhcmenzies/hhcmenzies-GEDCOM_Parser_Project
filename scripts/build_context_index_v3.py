#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# -----------------------------
# IO helpers
# -----------------------------
def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, obj: Any, *, pretty: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        if pretty:
            json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=True)
        else:
            json.dump(obj, f, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# -----------------------------
# Tag dictionaries
# -----------------------------
TAG_RE = re.compile(r"^[A-Z0-9_]{2,8}$")


def normalize_tag_key(s: str) -> str:
    return str(s).strip().upper()


def load_canonical_tag_dict(path: Path) -> Dict[str, Dict[str, Any]]:
    raw = read_json(path)
    # accepted shapes:
    # 1) {"tags": {"TAG": {...}}}
    # 2) {"TAG": {...}}  (direct mapping)
    if isinstance(raw, dict) and isinstance(raw.get("tags"), dict):
        return {normalize_tag_key(k): v for k, v in raw["tags"].items()}
    if isinstance(raw, dict):
        out = {}
        for k, v in raw.items():
            kk = normalize_tag_key(k)
            if TAG_RE.match(kk) and isinstance(v, dict):
                out[kk] = v
        if out:
            return out
    raise ValueError(f"Unrecognized canonical tag dictionary shape: {path}")


def load_schema_draft(path: Optional[Path]) -> Dict[str, Dict[str, Any]]:
    if not path:
        return {}
    if not path.exists():
        return {}
    raw = read_json(path)
    if isinstance(raw, dict) and isinstance(raw.get("tags"), dict):
        return {normalize_tag_key(k): v for k, v in raw["tags"].items()}
    if isinstance(raw, dict):
        return {normalize_tag_key(k): v for k, v in raw.items() if isinstance(v, dict)}
    return {}


def load_legacy_tags(path: Optional[Path]) -> Dict[str, Dict[str, Any]]:
    if not path:
        return {}
    if not path.exists():
        return {}
    raw = read_json(path)
    if isinstance(raw, dict) and isinstance(raw.get("tags"), dict):
        return {normalize_tag_key(k): v for k, v in raw["tags"].items()}
    if isinstance(raw, dict):
        return {normalize_tag_key(k): v for k, v in raw.items() if isinstance(v, dict)}
    if isinstance(raw, list):
        out = {}
        for item in raw:
            if isinstance(item, dict) and "tag" in item:
                out[normalize_tag_key(item["tag"])] = item
        return out
    return {}


# -----------------------------
# Canonical placements
# -----------------------------
PLACEMENT_PATH_KEYS = ("context_path", "path", "dot_path", "context")


def load_canonical_placements(path: Path) -> Tuple[List[Dict[str, Any]], List[str], List[Dict[str, Any]]]:
    raw = read_json(path)
    placements = raw.get("placements") if isinstance(raw, dict) and "placements" in raw else raw
    if not isinstance(placements, list):
        raise ValueError(f"Canonical placements is not a list: {path}")

    dot_paths: List[str] = []
    unnormalized: List[Dict[str, Any]] = []

    for item in placements:
        if not isinstance(item, dict):
            unnormalized.append({"_value": item})
            continue
        dp = None
        for k in PLACEMENT_PATH_KEYS:
            v = item.get(k)
            if isinstance(v, str) and v.strip():
                dp = v.strip().upper()
                break
        if dp:
            dot_paths.append(dp)
        else:
            unnormalized.append(item)

    # de-dupe stable
    seen = set()
    uniq = []
    for dp in dot_paths:
        if dp not in seen:
            seen.add(dp)
            uniq.append(dp)

    return placements, uniq, unnormalized


# -----------------------------
# Project structures
# -----------------------------
def load_project_structures(path: Optional[Path]) -> Dict[str, Dict[str, Any]]:
    if not path:
        return {}
    if not path.exists():
        return {}
    raw = read_json(path)
    if not isinstance(raw, dict):
        raise ValueError(f"Project structures must be a dict keyed by structure path: {path}")
    out: Dict[str, Dict[str, Any]] = {}
    for k, v in raw.items():
        if not isinstance(k, str):
            continue
        kk = k.strip().upper()
        out[kk] = v if isinstance(v, dict) else {"_value": v}
    return out


def expand_project_structures_to_paths(structs: Dict[str, Dict[str, Any]], max_depth: int) -> List[str]:
    """
    Your gedcom55_structures.json uses two conventions:
    - Some keys are already dot-paths: "FAM.ANUL"
    - Some keys are standalone tags: "ADDR"
    Each value has "children": {tag -> constraints} or "children": [ ... ] depending on generator.
    We'll support both.
    Depth meaning:
      max_depth=1 => only the key itself
      max_depth=2 => key + its children
      max_depth=3 => key + children + grandchildren
    """
    out = set()

    def add(p: str) -> None:
        out.add(p)

    # Helper: parse children into iterable (tag, child_obj)
    def iter_children(children: Any):
        if isinstance(children, dict):
            for t, obj in children.items():
                yield normalize_tag_key(t), obj
        elif isinstance(children, list):
            for obj in children:
                if isinstance(obj, dict) and "tag" in obj:
                    yield normalize_tag_key(obj["tag"]), obj
        else:
            return

    for skey, sval in structs.items():
        base = skey.strip().upper()
        add(base)

        if max_depth < 2:
            continue

        if not isinstance(sval, dict):
            continue

        children = sval.get("children")
        if children is None:
            continue

        for ctag, cobj in iter_children(children):
            p1 = f"{base}.{ctag}"
            add(p1)

            if max_depth < 3:
                continue

            # grandchildren
            if isinstance(cobj, dict):
                gc_children = cobj.get("children")
            else:
                gc_children = None
            if gc_children is None and isinstance(cobj, dict) and "children" in cobj:
                gc_children = cobj["children"]

            for gctag, _gcobj in iter_children(gc_children):
                add(f"{p1}.{gctag}")

    return sorted(out)


# -----------------------------
# Build context index
# -----------------------------
def record_root_from_path(dp: str) -> str:
    return dp.split(".", 1)[0].upper()


def tag_from_path(dp: str) -> str:
    return dp.split(".")[-1].upper()


def build_context_index(
    *,
    canonical_tags: Dict[str, Dict[str, Any]],
    canonical_dot_paths: List[str],
    project_dot_paths: List[str],
    schema_draft: Dict[str, Dict[str, Any]],
    legacy_tags: Dict[str, Dict[str, Any]],
    include_timestamp: bool,
) -> Dict[str, Any]:

    all_tags = set(canonical_tags.keys()) | set(schema_draft.keys()) | set(legacy_tags.keys())
    for dp in canonical_dot_paths + project_dot_paths:
        all_tags.add(tag_from_path(dp))
        all_tags.add(record_root_from_path(dp))

    # Merge metadata with precedence: legacy < schema_draft < canonical
    global_meta: Dict[str, Dict[str, Any]] = {}
    for t in sorted(all_tags):
        meta: Dict[str, Any] = {}
        if t in legacy_tags:
            meta.update(legacy_tags[t])
        if t in schema_draft:
            meta.update(schema_draft[t])
        if t in canonical_tags:
            meta.update(canonical_tags[t])
        global_meta[t] = meta

    contexts: Dict[str, Dict[str, Any]] = {}
    tag_to_paths: Dict[str, List[str]] = defaultdict(list)

    canonical_set = set(canonical_dot_paths)
    project_set = set(project_dot_paths)

    for dp in sorted(canonical_set | project_set):
        root = record_root_from_path(dp)
        tag = tag_from_path(dp)
        contexts[dp] = {
            "path": dp,
            "record_root": root,
            "tag": tag,
            "source": {"canonical": dp in canonical_set, "project_structures": dp in project_set},
        }
        tag_to_paths[tag].append(dp)

    roots = Counter(record_root_from_path(dp) for dp in contexts.keys())
    tags_with_paths = set(tag_to_paths.keys())

    # Tags without any placements (excluding record roots)
    tags_without_any_context_path = sorted(
        [t for t in global_meta.keys() if TAG_RE.match(t) and t not in tags_with_paths]
    )

    # Core field gaps
    missing_fields = []
    for t, meta in global_meta.items():
        if not TAG_RE.match(t):
            continue
        want = ["description", "category", "payload"]
        missing = [f for f in want if not meta.get(f)]
        if missing:
            missing_fields.append({"tag": t, "missing": missing})

    coverage = {
        "total_tags_global_metadata": len(global_meta),
        "total_context_paths": len(contexts),
        "record_root_counts": dict(roots),
        "tags_without_any_context_path": tags_without_any_context_path,
        "tags_missing_core_fields": missing_fields,
    }

    return {
        "_meta": {
            "generated_at": (datetime.utcnow().isoformat(timespec="seconds") + "Z") if include_timestamp else None,
            "inputs": {
                "canonical_tags_count": len(canonical_tags),
                "canonical_dot_paths_count": len(canonical_dot_paths),
                "project_dot_paths_count": len(project_dot_paths),
                "schema_draft_count": len(schema_draft),
                "legacy_tags_count": len(legacy_tags),
            },
        },
        "coverage": coverage,
        "contexts": contexts,
        "tag_to_context_paths": dict(sorted(tag_to_paths.items())),
        "global_tag_metadata": global_meta,
    }


# -----------------------------
# Reporting
# -----------------------------
def write_reports(report_dir: Path, index: Dict[str, Any], *, canonical_unnormalized: List[Dict[str, Any]]) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "coverage": index.get("coverage", {}),
        "canonical_placements_unnormalized_count": len(canonical_unnormalized),
        "canonical_placements_unnormalized_sample_keys": sorted(
            set(k for it in canonical_unnormalized[:25] for k in (it.keys() if isinstance(it, dict) else []))
        ),
    }
    write_json(report_dir / "context_index_coverage_report.json", report, pretty=True)

    cov = index.get("coverage", {})
    md = []
    md.append("# Context Index Coverage Report\n")
    md.append(f"- Total tag metadata entries: **{cov.get('total_tags_global_metadata', 0)}**")
    md.append(f"- Total context paths: **{cov.get('total_context_paths', 0)}**")
    md.append(f"- Canonical placements that could not be normalized: **{len(canonical_unnormalized)}**\n")
    md.append("## Record root counts\n")
    for k, v in sorted(cov.get("record_root_counts", {}).items()):
        md.append(f"- {k}: {v}")
    md.append("\n## Tags without any context path\n")
    twp = cov.get("tags_without_any_context_path", [])
    md.append(", ".join(twp[:160]) + (" …" if len(twp) > 160 else "") if twp else "_None_")
    md.append("\n\n## Tags missing core fields (description/category/payload)\n")
    tmf = cov.get("tags_missing_core_fields", [])
    if tmf:
        md.append(f"Count: {len(tmf)}\n")
        for row in tmf[:30]:
            md.append(f"- {row['tag']}: missing {', '.join(row['missing'])}")
    else:
        md.append("_None_")

    write_text(report_dir / "context_index_coverage_report.md", "\n".join(md))

    with (report_dir / "context_index_coverage_gaps.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["type", "tag_or_path", "details"])
        for t in cov.get("tags_without_any_context_path", []):
            w.writerow(["tag_without_context", t, ""])
        for row in cov.get("tags_missing_core_fields", []):
            w.writerow(["tag_missing_fields", row["tag"], ";".join(row["missing"])])
        if canonical_unnormalized:
            w.writerow(["canonical_placements_unnormalized", str(len(canonical_unnormalized)), "see JSON report sample keys"])


# -----------------------------
# CLI
# -----------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="Build tag_context_index.json deterministically with coverage reporting.")
    ap.add_argument("--canonical-tags", required=True, type=Path)
    ap.add_argument("--canonical-grammar", required=True, type=Path)
    ap.add_argument("--project-structures", type=Path, default=None)
    ap.add_argument("--schema-draft", type=Path, default=None)
    ap.add_argument("--legacy-tags", type=Path, default=None)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--report-dir", required=True, type=Path)
    ap.add_argument("--max-depth", type=int, default=3, help="Depth in segments: 2 children; 3 includes grandchildren")
    ap.add_argument("--no-timestamp", action="store_true")
    args = ap.parse_args()

    canonical_tags = load_canonical_tag_dict(args.canonical_tags)
    _placements, canonical_dot_paths, canonical_unnormalized = load_canonical_placements(args.canonical_grammar)

    schema_draft = load_schema_draft(args.schema_draft)
    legacy_tags = load_legacy_tags(args.legacy_tags)

    project_structs = load_project_structures(args.project_structures)
    project_dot_paths = expand_project_structures_to_paths(project_structs, max_depth=max(1, args.max_depth))

    index = build_context_index(
        canonical_tags=canonical_tags,
        canonical_dot_paths=canonical_dot_paths,
        project_dot_paths=project_dot_paths,
        schema_draft=schema_draft,
        legacy_tags=legacy_tags,
        include_timestamp=not args.no_timestamp,
    )

    write_json(args.out, index, pretty=True)
    write_reports(args.report_dir, index, canonical_unnormalized=canonical_unnormalized)

    print(f"Wrote context index: {args.out}")
    print(f"Wrote coverage report: {args.report_dir / 'context_index_coverage_report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
