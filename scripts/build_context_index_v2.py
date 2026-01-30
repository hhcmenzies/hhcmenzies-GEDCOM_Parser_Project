#!/usr/bin/env python3
"""
build_context_index_v2.py

Deterministically compiles a context-aware validator/enrichment map ("tag_context_index.json")
and emits a comprehensive coverage + drift report.

Why this exists
---------------
GEDCOM tags are *context dependent*; the same tag may be legal/illegal or have different
constraints depending on where it appears in the hierarchy. Therefore we treat:

    CONTEXT PATH  (e.g., "INDI.BIRT.DATE")

as the primary key for validation/enrichment rather than a flat tag list.

Inputs (recommended)
--------------------
1) Canonical spec-extracted inputs (source-of-truth):
   - canonical_tag_dictionary_gedcom551.json
       { "_meta": {...}, "tags": { "TAG": {...}, ... } }
   - canonical_grammar_placements_gedcom551.json
       { "_meta": {...}, "placements": [ { "path": "INDI.BIRT.DATE", ... }, ... ] }

2) Project grammar inputs (to compare against / augment constraints):
   - gedcom55_structures.json  (context structures; keys like "INDI.ADOP", "OBJE.FILE")
       { "INDI.ADOP": { "children": { "DATE": {...}, ... }, ... }, ... }

3) Optional tag metadata drafts/legacy:
   - gedcom55_schema_draft.json (flat tag metadata, parent/child hints)
   - gedcom_tags.json           (legacy list)

Outputs
-------
- tag_context_index.json
- coverage report: JSON + Markdown + CSV

Determinism
-----------
- All dict keys are output sorted.
- Timestamps may be suppressed (--no-timestamp) to keep Git diffs stable.

Notes
-----
- This script reports *two kinds of gaps*:
  (A) Canonical coverage gaps: tags/placements present in the spec inputs but missing in compiled contexts.
  (B) Project drift gaps: differences between spec placements and your project structures.

This is intentionally "audit-first": the report is designed to drive completion toward a
mathematically complete GEDCOM universe.
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
import json
import os
import re
import sys
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

JSONDict = Dict[str, Any]

# -------------------------
# Utilities
# -------------------------

def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=True)

def now_iso_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def is_todoish(s: Optional[str]) -> bool:
    if not s:
        return False
    return bool(re.search(r"\bTODO\b|\bTBD\b|Appendix\s+A", s, flags=re.IGNORECASE))

def stable_sorted(iterable: Iterable[str]) -> List[str]:
    return sorted(set(iterable))

def normalize_path(p: str) -> str:
    # Defensive normalization: remove accidental leading/trailing dots/spaces
    return ".".join([seg for seg in p.strip().strip(".").split(".") if seg])

def path_parent(p: str) -> Optional[str]:
    p = normalize_path(p)
    if "." not in p:
        return None
    return p.rsplit(".", 1)[0]

def path_tag(p: str) -> str:
    p = normalize_path(p)
    return p.split(".")[-1] if p else p

def path_root_record(p: str) -> str:
    p = normalize_path(p)
    return p.split(".", 1)[0] if p else ""

# -------------------------
# Structures expansion
# -------------------------

def expand_structures_to_paths(
    structures: JSONDict,
    max_depth: int = 2,
    record_roots: Optional[Set[str]] = None
) -> Tuple[Set[str], Dict[str, Dict[str, Any]], Set[str]]:
    """
    Expand gedcom55_structures.json (which is keyed by "CONTEXT.TAG" blocks)
    into explicit paths down to depth max_depth (root->child->grandchild = depth 2).

    Returns:
      - paths: set of explicit context paths discovered
      - path_constraints: mapping path -> constraint dict (min/max/payload/pointer_to) where known
      - unused_structure_keys: structure keys that were not reachable from the chosen record roots
    """
    # Build adjacency from structure keys. Each key is a "block" with its own children.
    # Example:
    #   key "INDI.ADOP" has children including "DATE"
    # We consider the implicit node "INDI.ADOP" and edges to "INDI.ADOP.DATE", etc.
    keys = set(structures.keys())

    if record_roots is None:
        # Conservative: only treat well-known record roots as roots for reachability.
        record_roots = {"HEAD", "INDI", "FAM", "SOUR", "REPO", "SUBM", "NOTE", "OBJE", "SUBN", "TRLR"}

    # Graph of block -> child paths
    block_children: Dict[str, Set[str]] = defaultdict(set)
    path_constraints: Dict[str, Dict[str, Any]] = {}

    for block, node in structures.items():
        b = normalize_path(block)
        children = (node or {}).get("children", {}) or {}
        for child_tag, cinfo in children.items():
            cpath = normalize_path(f"{b}.{child_tag}")
            block_children[b].add(cpath)
            # capture constraints for this specific child edge
            if isinstance(cinfo, dict):
                path_constraints[cpath] = {
                    k: cinfo.get(k) for k in ("min", "max", "payload", "pointer_to") if k in cinfo
                }
                # also keep raw for debugging
                path_constraints[cpath]["_source"] = "project_structures"

    # BFS from record roots along explicit child paths, limited by max_depth from root record.
    discovered_paths: Set[str] = set()
    visited_blocks: Set[str] = set()
    q: deque[str] = deque()

    # Seed: any block whose root is a record root.
    for b in keys:
        if path_root_record(b) in record_roots:
            q.append(normalize_path(b))

    while q:
        b = q.popleft()
        if b in visited_blocks:
            continue
        visited_blocks.add(b)

        # include the block itself as a "context node" (not necessarily a real GEDCOM tag placement)
        discovered_paths.add(b)

        # expand children if depth allows
        # depth measured as number of dots from root record
        depth = normalize_path(b).count(".")
        if depth >= max_depth:
            continue

        for cpath in stable_sorted(block_children.get(b, set())):
            discovered_paths.add(cpath)
            # The child may itself be a defined block (e.g., INDI.ADOP.DATE could have children)
            # If so, enqueue it for further expansion.
            if cpath in keys:
                q.append(cpath)

    unused = keys - visited_blocks
    return discovered_paths, path_constraints, unused

# -------------------------
# Canonical spec inputs
# -------------------------

@dataclasses.dataclass(frozen=True)
class CanonicalTag:
    tag: str
    formal_name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    payload: Optional[str] = None
    enums: Optional[List[str]] = None

@dataclasses.dataclass(frozen=True)
class CanonicalPlacement:
    path: str
    min: Optional[int] = None
    max: Optional[Any] = None
    payload: Optional[str] = None
    pointer_to: Optional[str] = None
    source: Optional[str] = None

def load_canonical_tag_dict(path: Path) -> Dict[str, CanonicalTag]:
    raw = read_json(path)
    tags = raw.get("tags", {})
    out: Dict[str, CanonicalTag] = {}
    for t, meta in tags.items():
        if not isinstance(meta, dict):
            meta = {}
        out[t] = CanonicalTag(
            tag=t,
            formal_name=meta.get("formal_name") or meta.get("name") or meta.get("title"),
            description=meta.get("description"),
            category=meta.get("category"),
            payload=meta.get("payload"),
            enums=meta.get("enums"),
        )
    return out

def load_canonical_placements(path: Path) -> List[CanonicalPlacement]:
    raw = read_json(path)
    pls = raw.get("placements", raw.get("paths", []))
    out: List[CanonicalPlacement] = []
    for item in pls:
        if isinstance(item, str):
            p = item
            meta = {}
        else:
            meta = item or {}
            p = meta.get("path") or meta.get("context") or ""
        p = normalize_path(p)
        if not p:
            continue
        out.append(CanonicalPlacement(
            path=p,
            min=meta.get("min"),
            max=meta.get("max"),
            payload=meta.get("payload"),
            pointer_to=meta.get("pointer_to"),
            source=meta.get("source") or meta.get("_source"),
        ))
    # Deterministic order
    out.sort(key=lambda x: x.path)
    return out

# -------------------------
# Optional draft inputs (for richer metadata + sanity)
# -------------------------

def load_schema_draft(path: Path) -> Dict[str, Dict[str, Any]]:
    raw = read_json(path)
    # draft is keyed by tag directly
    out: Dict[str, Dict[str, Any]] = {}
    for t, meta in raw.items():
        if isinstance(meta, dict):
            out[t] = meta
        else:
            out[t] = {}
    return out

def load_legacy_tags(path: Path) -> Dict[str, Dict[str, Any]]:
    raw = read_json(path)
    tags = raw.get("tags", raw)
    out = {}
    if isinstance(tags, list):
        for t in tags:
            if isinstance(t, str):
                out[t] = {}
            elif isinstance(t, dict) and "tag" in t:
                out[str(t["tag"])] = t
    elif isinstance(tags, dict):
        out = {str(k): (v if isinstance(v, dict) else {}) for k, v in tags.items()}
    return out

# -------------------------
# Index compilation
# -------------------------

def compile_context_index(
    canonical_tags: Dict[str, CanonicalTag],
    canonical_placements: List[CanonicalPlacement],
    max_depth: int,
    project_struct_paths: Optional[Set[str]] = None,
    project_constraints: Optional[Dict[str, Dict[str, Any]]] = None,
    schema_draft: Optional[Dict[str, Dict[str, Any]]] = None,
    legacy_tags: Optional[Dict[str, Dict[str, Any]]] = None,
) -> JSONDict:
    """
    Build tag_context_index.json structure.

    Priority for constraints:
      1) canonical placement constraints (if present)
      2) project structures constraints (if a matching explicit path exists)
      3) schema draft hints (allowed_parents/children etc. are metadata, not constraints)

    Metadata:
      canonical tag dict is primary; draft/legacy can fill missing fields.
    """
    schema_draft = schema_draft or {}
    legacy_tags = legacy_tags or {}
    project_constraints = project_constraints or {}

    contexts: Dict[str, Any] = {}
    tag_to_paths: Dict[str, List[str]] = defaultdict(list)

    # Build contexts from canonical placements, depth-limited.
    for plc in canonical_placements:
        p = normalize_path(plc.path)
        if p.count(".") > max_depth:
            continue
        tag = path_tag(p)
        root = path_root_record(p)
        parent = path_parent(p)

        # pull canonical tag metadata
        cmeta = canonical_tags.get(tag)

        # supplement from draft/legacy if missing
        dmeta = schema_draft.get(tag, {})
        lmeta = legacy_tags.get(tag, {})

        meta = {
            "tag": tag,
            "record_root": root,
            "parent_path": parent,
            "path": p,
            "level": p.count("."),
            "meta": {
                "formal_name": (cmeta.formal_name if cmeta else None) or dmeta.get("formal_name") or lmeta.get("formal_name"),
                "description": (cmeta.description if cmeta else None) or dmeta.get("description") or lmeta.get("description"),
                "category": (cmeta.category if cmeta else None) or dmeta.get("category") or lmeta.get("category"),
                "payload": (cmeta.payload if cmeta else None) or dmeta.get("payload") or lmeta.get("payload"),
                "enums": (cmeta.enums if cmeta else None) or dmeta.get("enums") or lmeta.get("enums"),
                # keep draft relationship hints if present
                "allowed_parents": dmeta.get("allowed_parents", []),
                "allowed_children": dmeta.get("allowed_children", []),
                "multiple": dmeta.get("multiple"),
                "required": dmeta.get("required"),
            },
            "constraints": {},
            "source": {
                "canonical_placement_source": plc.source,
                "canonical": True,
                "project_structures": False,
            }
        }

        # constraints: canonical first
        for k in ("min", "max", "payload", "pointer_to"):
            v = getattr(plc, k)
            if v is not None:
                meta["constraints"][k] = v

        # fill constraints from project structures if missing and available
        if p in project_constraints:
            for k, v in project_constraints[p].items():
                if k == "_source":
                    continue
                if k not in meta["constraints"] and v is not None:
                    meta["constraints"][k] = v
            meta["source"]["project_structures"] = True

        contexts[p] = meta
        tag_to_paths[tag].append(p)

    # Deterministic ordering for tag_to_paths
    tag_to_paths_sorted = {t: sorted(ps) for t, ps in sorted(tag_to_paths.items(), key=lambda kv: kv[0])}

    # Global tag metadata union view
    global_tag_metadata: Dict[str, Any] = {}
    for tag in sorted(set(list(canonical_tags.keys()) + list(schema_draft.keys()) + list(legacy_tags.keys()))):
        c = canonical_tags.get(tag)
        d = schema_draft.get(tag, {})
        l = legacy_tags.get(tag, {})
        global_tag_metadata[tag] = {
            "formal_name": (c.formal_name if c else None) or d.get("formal_name") or l.get("formal_name"),
            "description": (c.description if c else None) or d.get("description") or l.get("description"),
            "category": (c.category if c else None) or d.get("category") or l.get("category"),
            "payload": (c.payload if c else None) or d.get("payload") or l.get("payload"),
            "enums": (c.enums if c else None) or d.get("enums") or l.get("enums"),
        }

    index = {
        "_meta": {},
        "contexts": {k: contexts[k] for k in sorted(contexts.keys())},
        "tag_to_context_paths": tag_to_paths_sorted,
        "global_tag_metadata": global_tag_metadata,
    }
    return index

# -------------------------
# Coverage / drift reporting
# -------------------------

def build_coverage_report(
    canonical_tags: Dict[str, CanonicalTag],
    canonical_placements: List[CanonicalPlacement],
    index: JSONDict,
    project_struct_paths: Optional[Set[str]] = None,
    unused_structure_keys: Optional[Set[str]] = None,
    max_depth: int = 2,
) -> JSONDict:
    contexts = index.get("contexts", {})
    tags_in_context = set(index.get("tag_to_context_paths", {}).keys())
    all_tags = set(canonical_tags.keys())
    missing_tags = sorted(all_tags - tags_in_context)

    canonical_paths = sorted({p.path for p in canonical_placements if p.path.count(".") <= max_depth})
    built_paths = sorted(contexts.keys())
    built_path_set = set(built_paths)

    missing_canonical_paths = sorted(set(canonical_paths) - built_path_set)

    report: JSONDict = {
        "summary": {
            "canonical_total_tags": len(all_tags),
            "canonical_total_placements_leq_depth": len(canonical_paths),
            "built_total_context_paths": len(built_paths),
            "built_total_tags_with_paths": len(tags_in_context),
            "missing_tags_without_any_context_path": len(missing_tags),
            "missing_canonical_paths": len(missing_canonical_paths),
            "max_depth": max_depth,
        },
        "canonical_missing": {
            "tags_without_any_context_path": missing_tags,
            "paths_missing_from_index": missing_canonical_paths,
        },
        "metadata_quality": {},
        "project_drift": {},
    }

    # Metadata gaps: canonical tags missing description/formal_name etc (useful when extraction is incomplete)
    gaps = []
    for t, meta in canonical_tags.items():
        missing_fields = []
        if not meta.formal_name: missing_fields.append("formal_name")
        if not meta.description or is_todoish(meta.description): missing_fields.append("description")
        if not meta.category: missing_fields.append("category")
        if not meta.payload: missing_fields.append("payload")
        if missing_fields:
            gaps.append({"tag": t, "missing": missing_fields})
    report["metadata_quality"]["canonical_tags_missing_fields"] = gaps
    report["metadata_quality"]["canonical_tags_missing_fields_count"] = len(gaps)

    # Project drift comparisons
    if project_struct_paths is not None:
        project_set = set(project_struct_paths)
        canonical_set = set(canonical_paths)

        report["project_drift"] = {
            "project_paths_leq_depth": len(project_set),
            "spec_paths_leq_depth": len(canonical_set),
            "spec_paths_missing_in_project": sorted(canonical_set - project_set),
            "project_paths_not_in_spec": sorted(project_set - canonical_set),
        }
        if unused_structure_keys is not None:
            report["project_drift"]["unused_structure_keys"] = sorted(unused_structure_keys)
            report["project_drift"]["unused_structure_keys_count"] = len(unused_structure_keys)

    return report

def write_markdown_report(report: JSONDict, out_path: Path) -> None:
    s = report["summary"]
    lines = []
    lines.append("# Context Index Coverage Report\n")
    lines.append("## Summary\n")
    lines.append(f"- Canonical total tags: **{s['canonical_total_tags']}**")
    lines.append(f"- Canonical placements (<= depth {s['max_depth']}): **{s['canonical_total_placements_leq_depth']}**")
    lines.append(f"- Built context paths: **{s['built_total_context_paths']}**")
    lines.append(f"- Tags with at least one path: **{s['built_total_tags_with_paths']}**")
    lines.append(f"- Tags missing any path: **{s['missing_tags_without_any_context_path']}**")
    lines.append(f"- Canonical paths missing from index: **{s['missing_canonical_paths']}**\n")

    lines.append("## Canonical gaps\n")
    missing_tags = report["canonical_missing"]["tags_without_any_context_path"]
    if missing_tags:
        lines.append(f"### Tags with no context paths ({len(missing_tags)})")
        lines.append(", ".join(missing_tags) + "\n")
    missing_paths = report["canonical_missing"]["paths_missing_from_index"]
    if missing_paths:
        lines.append(f"### Canonical placements missing from index ({len(missing_paths)})")
        # keep markdown readable
        preview = missing_paths[:200]
        lines.append("\n".join([f"- `{p}`" for p in preview]))
        if len(missing_paths) > len(preview):
            lines.append(f"- ... and {len(missing_paths) - len(preview)} more\n")

    lines.append("## Metadata quality (canonical)\n")
    gaps = report["metadata_quality"]["canonical_tags_missing_fields"]
    lines.append(f"- Tags missing one or more fields: **{len(gaps)}**\n")
    if gaps:
        for g in gaps[:60]:
            lines.append(f"- `{g['tag']}` missing: {', '.join(g['missing'])}")
        if len(gaps) > 60:
            lines.append(f"- ... and {len(gaps) - 60} more\n")

    if report.get("project_drift"):
        d = report["project_drift"]
        lines.append("## Project drift vs spec (depth-limited)\n")
        lines.append(f"- Project paths (<= depth): **{d.get('project_paths_leq_depth', 0)}**")
        lines.append(f"- Spec paths (<= depth): **{d.get('spec_paths_leq_depth', 0)}**")
        lines.append(f"- Spec paths missing in project: **{len(d.get('spec_paths_missing_in_project', []))}**")
        lines.append(f"- Project paths not in spec: **{len(d.get('project_paths_not_in_spec', []))}**\n")

        if "unused_structure_keys_count" in d:
            lines.append(f"- Unused structure keys: **{d['unused_structure_keys_count']}**\n")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")

def write_csv_gaps(missing_paths: List[str], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["missing_path"])
        for p in missing_paths:
            w.writerow([p])

# -------------------------
# CLI
# -------------------------

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--canonical-tags", type=Path, required=True, help="canonical tag dictionary JSON")
    ap.add_argument("--canonical-grammar", type=Path, required=True, help="canonical placements JSON")
    ap.add_argument("--project-structures", type=Path, default=None, help="project structures JSON to compare/augment")
    ap.add_argument("--schema-draft", type=Path, default=None, help="optional draft schema metadata JSON")
    ap.add_argument("--legacy-tags", type=Path, default=None, help="optional legacy tags JSON")
    ap.add_argument("--out", type=Path, required=True, help="output tag_context_index.json path")
    ap.add_argument("--report-dir", type=Path, required=True, help="directory for coverage outputs")
    ap.add_argument("--max-depth", type=int, default=2, help="expand/limit paths to this depth (0=root)")
    ap.add_argument("--no-timestamp", action="store_true", help="suppress timestamps for git-stable outputs")
    return ap.parse_args()

def main() -> int:
    args = parse_args()

    canonical_tags = load_canonical_tag_dict(args.canonical_tags)
    canonical_placements = load_canonical_placements(args.canonical_grammar)

    schema_draft = load_schema_draft(args.schema_draft) if args.schema_draft else {}
    legacy = load_legacy_tags(args.legacy_tags) if args.legacy_tags else {}

    project_paths = None
    project_constraints = None
    unused_keys = None
    if args.project_structures:
        structures = read_json(args.project_structures)
        project_paths, project_constraints, unused_keys = expand_structures_to_paths(
            structures, max_depth=args.max_depth
        )

    index = compile_context_index(
        canonical_tags=canonical_tags,
        canonical_placements=canonical_placements,
        max_depth=args.max_depth,
        project_struct_paths=project_paths,
        project_constraints=project_constraints,
        schema_draft=schema_draft,
        legacy_tags=legacy,
    )

    # meta block
    index["_meta"] = {
        "generated_at": None if args.no_timestamp else now_iso_utc(),
        "inputs": {
            "canonical_tags": str(args.canonical_tags),
            "canonical_grammar": str(args.canonical_grammar),
            "project_structures": str(args.project_structures) if args.project_structures else None,
            "schema_draft": str(args.schema_draft) if args.schema_draft else None,
            "legacy_tags": str(args.legacy_tags) if args.legacy_tags else None,
        },
        "max_depth": args.max_depth,
        "deterministic": True,
    }

    write_json(args.out, index)

    report = build_coverage_report(
        canonical_tags=canonical_tags,
        canonical_placements=canonical_placements,
        index=index,
        project_struct_paths=project_paths,
        unused_structure_keys=unused_keys,
        max_depth=args.max_depth,
    )

    args.report_dir.mkdir(parents=True, exist_ok=True)
    write_json(args.report_dir / "context_index_coverage_report.json", report)
    write_markdown_report(report, args.report_dir / "context_index_coverage_report.md")
    write_csv_gaps(report["canonical_missing"]["paths_missing_from_index"],
                   args.report_dir / "context_index_coverage_gaps.csv")

    print(f"Wrote context index: {args.out}")
    print(f"Wrote coverage report: {args.report_dir / 'context_index_coverage_report.json'}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
