"""
place_hierarchy_builder.py

C.24.6 – Place Hierarchy Builder (Deterministic / Offline)

Input : C.24.5 canonical export JSON (must include root["places"] and per-event "place_id")
Output: Same registry shape, plus:
  - Hierarchy fields in root["places"][place_id]
      parts, parent_id, ancestor_ids, child_ids, levels (heuristic),
      generated (for synthetic suffix nodes), generated_from (source leaf)
  - Optional per-event derived block:
      event["place_hierarchy"] = {place_id, parent_id, ancestor_ids}

Design goals
-----------
- Works directly on modern export JSON dicts (no dataclasses, no pydantic).
- Never deletes or restructures existing data.
- Additive + idempotent: safe to run multiple times.
- Deterministic (no external APIs / geocoders).
- Conservative: does not "guess" geography beyond basic positional heuristics.

Key upgrade vs earlier draft:
-----------------------------
This module *canonicalizes* place IDs before building hierarchy to prevent
duplicate logical places caused by comma-spacing differences, e.g.:

  "lawrence,essex,massachusetts,usa"  vs  "lawrence, essex, massachusetts, usa"

If the IDs differ only by whitespace, we merge them safely and update all event
place_id references accordingly.

Counts policy
-------------
- Leaf counts remain leaf-accurate (from C.24.5 place_registry_builder).
- We DO NOT roll up counts into ancestors by default.
"""

from __future__ import annotations

import argparse
import json
from typing import Any, Dict, List, Optional, Tuple, Set

from gedcom_parser.logger import get_logger

log = get_logger("place_hierarchy_builder")


# -----------------------------------------------------------------------------
# Helpers: normalization & IDs
# -----------------------------------------------------------------------------

def _clean_str(s: Any) -> Optional[str]:
    if s is None:
        return None
    out = " ".join(str(s).split()).strip()
    return out or None


def _split_place_parts(text: str) -> List[str]:
    """
    Split a place string on commas into non-empty trimmed parts.
    Deterministic and conservative.
    """
    raw = _clean_str(text) or ""
    if not raw:
        return []
    parts = [p.strip() for p in raw.split(",")]
    parts = [" ".join(p.split()).strip() for p in parts]
    return [p for p in parts if p]


def _canonical_place_id_from_parts(parts: List[str]) -> str:
    """
    Canonical ID rules (C.24.5+):
      - lowercase
      - join by ", " (comma + single space)
      - collapse whitespace within parts
    """
    norm = ", ".join([" ".join(str(p).split()).strip() for p in parts if p and str(p).strip()])
    return norm.lower().strip()


def _canonical_place_id_from_text(text: str) -> Optional[str]:
    parts = _split_place_parts(text)
    if not parts:
        return None
    return _canonical_place_id_from_parts(parts)


def _equivalent_ids_whitespace_only(a: str, b: str) -> bool:
    """
    Safe equivalence check: treat ids as equivalent if they match after
    removing all whitespace (commas and characters remain).
    """
    return a.replace(" ", "") == b.replace(" ", "")


def _parts_dict(parts: List[str]) -> Dict[str, str]:
    """Position-based parts mapping (always safe). p0 most specific."""
    return {f"p{i}": p for i, p in enumerate(parts)}


def _heuristic_levels(parts: List[str]) -> Dict[str, str]:
    """
    Conservative heuristic mapping from positional parts to semantic-ish levels.
    Optional metadata, NOT authoritative.
    """
    p = [x for x in parts if x]
    n = len(p)
    levels: Dict[str, str] = {}
    if n == 1:
        levels["country"] = p[-1]
    elif n == 2:
        levels["region"] = p[-2]
        levels["country"] = p[-1]
    elif n == 3:
        levels["locality"] = p[-3]
        levels["region"] = p[-2]
        levels["country"] = p[-1]
    elif n >= 4:
        levels["locality"] = p[0]
        levels["county"] = p[1]
        levels["region"] = p[-2]
        levels["country"] = p[-1]
    return levels


def _pick_place_display_text(place_rec: Dict[str, Any]) -> Optional[str]:
    """
    Choose a stable display string for parsing parts:
      - prefer "normalized"
      - else any raw_example
      - else fall back to "id"
    """
    norm = _clean_str(place_rec.get("normalized"))
    if norm:
        return norm

    raw_examples = place_rec.get("raw_examples")
    if isinstance(raw_examples, list) and raw_examples:
        re0 = _clean_str(raw_examples[0])
        if re0:
            return re0

    pid = _clean_str(place_rec.get("id"))
    return pid


def _safe_append_unique(lst: List[str], value: str, max_len: int) -> None:
    if value in lst:
        return
    if len(lst) >= max_len:
        return
    lst.append(value)


def _merge_place_records(dst: Dict[str, Any], src: Dict[str, Any]) -> None:
    """
    Merge src into dst without losing data.

    - Preserve richer existing fields in dst.
    - Combine raw_examples, aliases.
    - Sum counts.
    """
    # Basic fields: keep dst unless missing
    for k in ("normalized", "parent_id", "hierarchy_confidence"):
        if not dst.get(k) and src.get(k):
            dst[k] = src[k]

    # raw_examples
    if isinstance(src.get("raw_examples"), list):
        dst_re = dst.get("raw_examples")
        if not isinstance(dst_re, list):
            dst_re = []
            dst["raw_examples"] = dst_re
        for v in src["raw_examples"]:
            vv = _clean_str(v)
            if vv:
                _safe_append_unique(dst_re, vv, max_len=25)

    # aliases
    if isinstance(src.get("aliases"), list):
        dst_al = dst.get("aliases")
        if not isinstance(dst_al, list):
            dst_al = []
            dst["aliases"] = dst_al
        for v in src["aliases"]:
            vv = _clean_str(v)
            if vv:
                _safe_append_unique(dst_al, vv, max_len=50)

    # counts: sum
    if isinstance(src.get("counts"), dict):
        dst_ct = dst.get("counts")
        if not isinstance(dst_ct, dict):
            dst_ct = {"events": 0, "individual_events": 0, "family_events": 0}
            dst["counts"] = dst_ct
        for ck in ("events", "individual_events", "family_events"):
            sv = src["counts"].get(ck)
            if isinstance(sv, int):
                dst_ct[ck] = int(dst_ct.get(ck) or 0) + sv

    # parts/levels/ancestor_ids/child_ids: keep dst if present, else take src
    for k in ("parts", "levels", "ancestor_ids", "child_ids"):
        if (k not in dst or not dst.get(k)) and src.get(k):
            dst[k] = src[k]

    # Preserve generated flags if either says generated
    if src.get("generated") is True:
        dst["generated"] = True
    if src.get("generated_from") and not dst.get("generated_from"):
        dst["generated_from"] = src["generated_from"]


# -----------------------------------------------------------------------------
# Pass 0: canonicalize place IDs and update references
# -----------------------------------------------------------------------------

def _canonicalize_places_and_rewrite_references(root: Dict[str, Any], metrics: Dict[str, int]) -> None:
    """
    Rebuild root["places"] keyed by canonical IDs when safe to do so, and rewrite
    all event place_id references accordingly.

    Safety rule: only merge when old_id and canonical_id differ *only* by whitespace.
    """
    places = root.get("places")
    if not isinstance(places, dict):
        return

    id_map: Dict[str, str] = {}  # old_id -> canonical_id
    for old_id, rec in list(places.items()):
        if not isinstance(old_id, str):
            continue
        if not isinstance(rec, dict):
            continue

        display = _pick_place_display_text(rec) or old_id
        canonical = _canonical_place_id_from_text(display) or _canonical_place_id_from_text(old_id) or old_id

        # If record's own id differs, prefer canonical computed from display
        if isinstance(rec.get("id"), str):
            rid = rec["id"]
            if _equivalent_ids_whitespace_only(rid, canonical):
                canonical = canonical  # keep
            # If wildly different, we do NOT remap automatically.

        if canonical != old_id and _equivalent_ids_whitespace_only(old_id, canonical):
            id_map[old_id] = canonical

    if not id_map:
        return

    # Rebuild places with merges
    new_places: Dict[str, Any] = {}
    for old_id, rec in list(places.items()):
        if not isinstance(old_id, str) or not isinstance(rec, dict):
            continue

        target = id_map.get(old_id, old_id)
        if target not in new_places:
            new_places[target] = rec
        else:
            _merge_place_records(new_places[target], rec)
            metrics["places_merged"] += 1

        # Ensure id field matches key
        if isinstance(new_places[target], dict):
            new_places[target]["id"] = target
            # Keep alias of old id if it changed
            if target != old_id:
                al = new_places[target].get("aliases")
                if not isinstance(al, list):
                    al = []
                    new_places[target]["aliases"] = al
                _safe_append_unique(al, old_id, max_len=50)

    # Replace root places
    root["places"] = new_places
    metrics["place_ids_canonicalized"] += len(id_map)

    # Rewrite event place_id references
    def _rewrite_events_in_group(group: Any) -> None:
        if not isinstance(group, dict):
            return
        for _k, rec in group.items():
            if not isinstance(rec, dict):
                continue
            evs = rec.get("events")
            if not isinstance(evs, list):
                continue
            for ev in evs:
                if not isinstance(ev, dict):
                    continue
                pid = ev.get("place_id")
                if isinstance(pid, str) and pid in id_map:
                    ev["place_id"] = id_map[pid]
                    metrics["event_place_ids_rewritten"] += 1

    _rewrite_events_in_group(root.get("individuals", {}))
    _rewrite_events_in_group(root.get("families", {}))


# -----------------------------------------------------------------------------
# Core: ensure nodes, build links
# -----------------------------------------------------------------------------

def _ensure_place_node(
    places: Dict[str, Any],
    place_id: str,
    display_text: Optional[str],
    generated_from: Optional[str] = None,
) -> Tuple[Dict[str, Any], bool]:
    created = False
    rec = places.get(place_id)
    if not isinstance(rec, dict):
        rec = {"id": place_id}
        places[place_id] = rec
        created = True

    if display_text and not rec.get("normalized"):
        rec["normalized"] = display_text

    # aliases
    aliases = rec.get("aliases")
    if not isinstance(aliases, list):
        aliases = []
        rec["aliases"] = aliases
    if display_text:
        norm = _clean_str(rec.get("normalized"))
        if norm and display_text != norm:
            _safe_append_unique(aliases, display_text, max_len=25)

    if generated_from:
        rec["generated"] = True
        if not rec.get("generated_from"):
            rec["generated_from"] = generated_from

    rec["id"] = place_id  # keep consistent

    return rec, created


def _suffix_ids_and_suffix_parts(parts: List[str]) -> List[Tuple[str, List[str]]]:
    """
    For parts [A,B,C,D], returns:
      [
        ("a, b, c, d", [A,B,C,D]),
        ("b, c, d", [B,C,D]),
        ("c, d", [C,D]),
        ("d", [D]),
      ]
    """
    out: List[Tuple[str, List[str]]] = []
    for i in range(len(parts)):
        sub = parts[i:]
        sid = _canonical_place_id_from_parts(sub)
        if sid:
            out.append((sid, sub))
    return out


def _build_ancestor_chain(
    place_id: str,
    parent_map: Dict[str, Optional[str]],
    max_depth: int = 64,
) -> Tuple[List[str], bool]:
    ancestors: List[str] = []
    seen: Set[str] = set()
    cur = parent_map.get(place_id)

    depth = 0
    cycle = False
    while cur and depth < max_depth:
        if cur in seen:
            cycle = True
            break
        seen.add(cur)
        ancestors.append(cur)
        cur = parent_map.get(cur)
        depth += 1

    return ancestors, cycle


# -----------------------------------------------------------------------------
# Main builder
# -----------------------------------------------------------------------------

def build_place_hierarchy(root: Dict[str, Any], enrich_events: bool = True) -> Dict[str, int]:
    metrics: Dict[str, int] = {
        "places_input": 0,
        "places_updated": 0,
        "synthetic_places_created": 0,
        "places_merged": 0,
        "place_ids_canonicalized": 0,
        "event_place_ids_rewritten": 0,
        "parent_links_set": 0,
        "ancestor_chains_set": 0,
        "child_links_set": 0,
        "cycles_detected": 0,
        "events_seen": 0,
        "events_enriched": 0,
        "events_missing_place_id": 0,
        "skipped_non_dict_events": 0,
    }

    if not isinstance(root, dict):
        return metrics

    places = root.get("places")
    if not isinstance(places, dict):
        places = {}
        root["places"] = places

    # Step 0: Canonicalize IDs + rewrite references (critical correctness)
    _canonicalize_places_and_rewrite_references(root, metrics)
    places = root.get("places", {})  # refresh reference
    if not isinstance(places, dict):
        places = {}
        root["places"] = places

    # Step 1: For each place, derive parts and ensure suffix nodes exist; build parent_map.
    parent_map: Dict[str, Optional[str]] = {}
    initial_ids = [pid for pid in places.keys() if isinstance(pid, str)]
    metrics["places_input"] = len(initial_ids)

    for place_id in initial_ids:
        rec_any = places.get(place_id)
        if not isinstance(rec_any, dict):
            continue

        display_text = _pick_place_display_text(rec_any) or place_id
        parts = _split_place_parts(display_text)

        if not parts:
            continue

        updated_this = False

        # Ensure normalized (keep original casing for display; id remains lowercase)
        if not rec_any.get("normalized"):
            rec_any["normalized"] = ", ".join(parts)
            updated_this = True

        # Ensure parts mapping
        if not isinstance(rec_any.get("parts"), dict) or not rec_any["parts"]:
            rec_any["parts"] = _parts_dict(parts)
            updated_this = True

        # Ensure heuristic levels
        if not isinstance(rec_any.get("levels"), dict) or not rec_any["levels"]:
            rec_any["levels"] = _heuristic_levels(parts)
            updated_this = True

        # Ensure suffix nodes
        suffix_chain = _suffix_ids_and_suffix_parts(parts)
        # Parent is second item in chain if present
        parent_id = suffix_chain[1][0] if len(suffix_chain) >= 2 else None
        parent_map[place_id] = parent_id

        # Create all suffix nodes (excluding leaf itself)
        for sid, subparts in suffix_chain[1:]:
            if sid not in places:
                synth_display = ", ".join(subparts)
                _ensure_place_node(places, sid, synth_display, generated_from=place_id)
                metrics["synthetic_places_created"] += 1

        if updated_this:
            metrics["places_updated"] += 1

    # Step 2: Ensure every node (including synthetic) is in parent_map
    for pid, rec in list(places.items()):
        if not isinstance(pid, str) or pid in parent_map:
            continue
        if not isinstance(rec, dict):
            parent_map[pid] = None
            continue

        display_text = _pick_place_display_text(rec) or pid
        parts = _split_place_parts(display_text)
        if not parts:
            parent_map[pid] = None
            continue

        suffix_chain = _suffix_ids_and_suffix_parts(parts)
        parent_map[pid] = suffix_chain[1][0] if len(suffix_chain) >= 2 else None

    # Step 3: Write parent_id and ancestor_ids (cycle-safe)
    for pid, parent_id in parent_map.items():
        rec = places.get(pid)
        if not isinstance(rec, dict):
            continue

        if parent_id and rec.get("parent_id") != parent_id:
            rec["parent_id"] = parent_id
            metrics["parent_links_set"] += 1

        ancestors, cycle = _build_ancestor_chain(pid, parent_map)
        if cycle:
            metrics["cycles_detected"] += 1
            rec["hierarchy_confidence"] = "broken_cycle"
        else:
            if not rec.get("hierarchy_confidence"):
                rec["hierarchy_confidence"] = "heuristic"

        if rec.get("ancestor_ids") != ancestors:
            rec["ancestor_ids"] = ancestors
            metrics["ancestor_chains_set"] += 1

    # Step 4: Build child_ids from scratch each run
    child_index: Dict[str, List[str]] = {}
    for pid, parent_id in parent_map.items():
        if parent_id:
            child_index.setdefault(parent_id, []).append(pid)

    for pid, rec_any in list(places.items()):
        if not isinstance(rec_any, dict):
            continue
        kids = sorted(set(child_index.get(pid, [])))
        if rec_any.get("child_ids") != kids:
            rec_any["child_ids"] = kids
            metrics["child_links_set"] += 1

    # Step 5: Optional per-event enrichment
    if enrich_events:
        def _enrich_events_in_group(group: Any) -> None:
            if not isinstance(group, dict):
                return
            for _k, rec in group.items():
                if not isinstance(rec, dict):
                    continue
                evs = rec.get("events")
                if not isinstance(evs, list):
                    continue
                for ev in evs:
                    metrics["events_seen"] += 1
                    if not isinstance(ev, dict):
                        metrics["skipped_non_dict_events"] += 1
                        continue

                    pid = ev.get("place_id")
                    if not pid:
                        metrics["events_missing_place_id"] += 1
                        continue

                    pid = str(pid)
                    parent_id = parent_map.get(pid)
                    ancestors = None
                    place_rec = places.get(pid)
                    if isinstance(place_rec, dict) and isinstance(place_rec.get("ancestor_ids"), list):
                        ancestors = place_rec["ancestor_ids"]
                    else:
                        ancestors, _ = _build_ancestor_chain(pid, parent_map)

                    block = {
                        "place_id": pid,
                        "parent_id": parent_id,
                        "ancestor_ids": ancestors,
                    }
                    if ev.get("place_hierarchy") != block:
                        ev["place_hierarchy"] = block
                        metrics["events_enriched"] += 1

        _enrich_events_in_group(root.get("individuals", {}))
        _enrich_events_in_group(root.get("families", {}))

    return metrics


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="C.24.6 – Place hierarchy builder (offline, deterministic)")
    p.add_argument("-i", "--input", required=True, help="Input JSON (C.24.5 export, e.g. outputs/export_c24_5.json)")
    p.add_argument("-o", "--output", required=True, help="Output JSON with place hierarchy (e.g. outputs/export_c24_6.json)")
    p.add_argument("--no-event-enrich", action="store_true", help="Do not add per-event place_hierarchy blocks")
    p.add_argument("--debug", action="store_true", help="Enable debug logging")
    return p


def main(argv: Optional[List[str]] = None) -> None:
    args = build_arg_parser().parse_args(argv)

    if args.debug:
        log.setLevel("DEBUG")

    log.info("Loading input JSON: %s", args.input)
    with open(args.input, "r", encoding="utf-8") as f:
        root = json.load(f)

    metrics = build_place_hierarchy(root, enrich_events=not args.no_event_enrich)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(root, f, ensure_ascii=False, indent=2)

    log.info(
        "Place hierarchy build complete: places_input=%d places_updated=%d synthetic_places_created=%d "
        "places_merged=%d place_ids_canonicalized=%d event_place_ids_rewritten=%d "
        "parent_links_set=%d ancestor_chains_set=%d child_links_set=%d cycles_detected=%d "
        "events_seen=%d events_enriched=%d events_missing_place_id=%d skipped_non_dict_events=%d",
        metrics["places_input"],
        metrics["places_updated"],
        metrics["synthetic_places_created"],
        metrics["places_merged"],
        metrics["place_ids_canonicalized"],
        metrics["event_place_ids_rewritten"],
        metrics["parent_links_set"],
        metrics["ancestor_chains_set"],
        metrics["child_links_set"],
        metrics["cycles_detected"],
        metrics["events_seen"],
        metrics["events_enriched"],
        metrics["events_missing_place_id"],
        metrics["skipped_non_dict_events"],
    )
    print(f"[INFO] Place hierarchy export written to: {args.output}")


if __name__ == "__main__":
    main()
