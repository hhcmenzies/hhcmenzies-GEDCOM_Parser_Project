"""
C.24.4.10 - Entity Resolution / Duplicate Detection (Individuals v1.1)

This module now implements:
- REAL blocking + similarity scoring for INDIVIDUALS.
- Skeleton stubs for FAMILIES and EVENTS (no real candidates yet).

Pipeline position (recommended input):
  1) main                  → export.json
  2) xref_resolver         → export_xref.json
  3) place_standardizer    → export_standardized.json
  4) event_disambiguator   → export_events_resolved.json
  5) event_scoring         → export_scored.json   (input here)
  6) entity_resolution     → export_entities_resolved.json + candidates + summary

Expected input registry (export_scored.json):

{
    "individuals":  { "<indi_id>": { ... }, ... },
    "families":     { "<fam_id>":  { ... }, ... },
    "sources":      { ... },
    "repositories": { ... },
    "media_objects":{ ... },
    "uuid_index":   { ... }      # from xref_resolver
}
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import difflib
from typing import Any, Dict, Iterable, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

try:
    from gedcom_parser.logging import get_logger  # type: ignore[attr-defined]
except Exception:  # fallback if project logger isn't importable

    def get_logger(name: str) -> logging.Logger:
        logging.basicConfig(
            level=logging.INFO,
            format="[%(asctime)s] %(levelname)-8s %(name)s: %(message)s",
            datefmt="%m/%d/%y %H:%M:%S",
        )
        return logging.getLogger(name)

log = get_logger("entity_resolution")

# ---------------------------------------------------------------------------
# Global thresholds / defaults (CLI can override)
# ---------------------------------------------------------------------------

DEFAULT_MIN_SCORE = 0.75
DEFAULT_AUTO_MERGE_THRESHOLD = 0.92
DEFAULT_REVIEW_THRESHOLD = 0.80
DEFAULT_MAX_PAIRS = 200_000


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def safe_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def normalize_token(token: str) -> str:
    """Basic normalizer for name/place tokens."""
    return re.sub(r"[^a-z0-9]+", "", token.lower()) if token else ""


def jaro_ratio(a: str, b: str) -> float:
    """Use SequenceMatcher as a reasonable proxy for fuzzy similarity."""
    a = a or ""
    b = b or ""
    if not a and not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


# ---------------------------------------------------------------------------
# Individual field extraction helpers
# ---------------------------------------------------------------------------

def extract_primary_name(person: Dict[str, Any]) -> Tuple[str, str]:
    """
    Return (given, surname) for the primary name, if available.
    GEDCOM-derived JSON usually has:
        person["names"] = [
            {"given": "...", "surname": "...", "type": "primary", ...}, ...
        ]
    We fall back to the first name if no explicit primary type is present.
    """
    names = person.get("names", [])
    if not isinstance(names, list) or not names:
        return "", ""

    primary = None
    for n in names:
        if isinstance(n, dict) and n.get("type", "").lower() == "primary":
            primary = n
            break

    if primary is None:
        primary = names[0]

    given = safe_str(primary.get("given"))
    surname = safe_str(primary.get("surname"))
    return given, surname


def extract_normalized_given_surname(person: Dict[str, Any]) -> Tuple[str, str]:
    given, surname = extract_primary_name(person)
    return normalize_token(given), normalize_token(surname)


def extract_birth_event(person: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Find the best birth-like event for this person.

    Order of preference:
      - tag == "BIRT"
      - tag in {"CHR", "BAPM"} as fallback
    """
    events = person.get("events", [])
    if not isinstance(events, list):
        return None

    birth = None
    christen = None

    for evt in events:
        if not isinstance(evt, dict):
            continue
        tag = safe_str(evt.get("tag")).upper()
        if tag == "BIRT":
            return evt
        if tag in {"CHR", "BAPM"} and christen is None:
            christen = evt

    return birth or christen


def _extract_date_field(date_obj: Any) -> str:
    """
    Try to normalize a date object from the event into a
    string we can scan for a year.
    """
    if isinstance(date_obj, dict):
        # Common patterns from your pipeline:
        for key in ("normalized", "value", "raw", "original"):
            if key in date_obj:
                return safe_str(date_obj[key])
        # Fallback to JSON of dict
        return safe_str(date_obj)
    else:
        return safe_str(date_obj)


def extract_birth_year(person: Dict[str, Any]) -> Optional[int]:
    evt = extract_birth_event(person)
    if not evt:
        return None
    date_obj = evt.get("date")
    if not date_obj:
        return None

    text = _extract_date_field(date_obj)
    m = re.search(r"(\d{4})", text)
    if not m:
        return None
    try:
        year = int(m.group(1))
    except ValueError:
        return None
    return year


def extract_birth_year_bucket(person: Dict[str, Any]) -> str:
    """
    Return a coarse birth-year bucket string.
    Example: "1880" (exact), "1880s", "UNKNOWN".
    For blocking we just need something stable-ish; we will use the
    exact year if we can parse it, otherwise "UNKNOWN".
    """
    year = extract_birth_year(person)
    if year is None:
        return "UNKNOWN"
    # You *could* put them in decade buckets; for now keep exact year.
    return str(year)


def extract_birth_place_uuid(person: Dict[str, Any]) -> str:
    """
    Use the standard_place.id from the birth event if present.
    Fallback: normalized raw place string.
    """
    evt = extract_birth_event(person)
    if not evt:
        return "UNKNOWN"

    std = evt.get("standard_place")
    if isinstance(std, dict):
        pid = safe_str(std.get("id"))
        if pid:
            return pid

    raw_place = safe_str(evt.get("place"))
    if not raw_place:
        return "UNKNOWN"

    return normalize_token(raw_place)


# ---------------------------------------------------------------------------
# Blocking for individuals
# ---------------------------------------------------------------------------

def individual_blocking_key(person: Dict[str, Any]) -> str:
    """
    Blocking key based on:
      - normalized surname
      - birth year bucket
      - birth place UUID (standardized)
    """
    given_n, surname_n = extract_normalized_given_surname(person)
    year_bucket = extract_birth_year_bucket(person)
    place_id = extract_birth_place_uuid(person)
    # We intentionally ignore given name for blocking; it's used in scoring.
    return f"{surname_n}|{year_bucket}|{place_id}"


def build_individual_blocks(individuals: Dict[str, Any]) -> Dict[str, List[str]]:
    blocks: Dict[str, List[str]] = {}

    for iid, person in individuals.items():
        if not isinstance(person, dict):
            continue
        key = individual_blocking_key(person)
        blocks.setdefault(key, []).append(iid)

    log.info(
        "Individual blocking: built %d blocks from %d individuals",
        len(blocks), len(individuals),
    )
    return blocks


def generate_block_pairs(blocks: Dict[str, List[str]], max_pairs: int) -> List[Tuple[str, str]]:
    """
    Generate candidate pairs within each block.
    """
    pairs: List[Tuple[str, str]] = []

    for _, ids in blocks.items():
        n = len(ids)
        if n < 2:
            continue
        for i in range(n):
            for j in range(i + 1, n):
                pairs.append((ids[i], ids[j]))
                if len(pairs) >= max_pairs:
                    return pairs

    return pairs


# ---------------------------------------------------------------------------
# Similarity scoring for individuals
# ---------------------------------------------------------------------------

def name_similarity(p1: Dict[str, Any], p2: Dict[str, Any]) -> float:
    g1, s1 = extract_normalized_given_surname(p1)
    g2, s2 = extract_normalized_given_surname(p2)

    if not s1 and not s2 and not g1 and not g2:
        return 0.0

    surname_score = jaro_ratio(s1, s2) if (s1 or s2) else 0.0
    given_score = jaro_ratio(g1, g2) if (g1 or g2) else 0.0

    # Surnames usually carry more weight in genealogy matching.
    return 0.6 * surname_score + 0.4 * given_score


def birth_similarity(p1: Dict[str, Any], p2: Dict[str, Any]) -> float:
    y1 = extract_birth_year(p1)
    y2 = extract_birth_year(p2)

    if y1 is None or y2 is None:
        return 0.0

    diff = abs(y1 - y2)
    if diff == 0:
        return 1.0
    if diff <= 1:
        return 0.9
    if diff <= 3:
        return 0.7
    if diff <= 10:
        return 0.4
    return 0.0


def place_similarity(p1: Dict[str, Any], p2: Dict[str, Any]) -> float:
    """
    Compare birth places using standard_place.id if available,
    else using normalized raw place strings.
    """
    evt1 = extract_birth_event(p1)
    evt2 = extract_birth_event(p2)
    if not evt1 or not evt2:
        return 0.0

    std1 = evt1.get("standard_place") or {}
    std2 = evt2.get("standard_place") or {}

    pid1 = safe_str(std1.get("id"))
    pid2 = safe_str(std2.get("id"))

    if pid1 and pid2:
        if pid1 == pid2:
            return 1.0
        # same id namespace, different value -> treat as different
        return 0.0

    # fallback: raw place strings
    raw1 = normalize_token(safe_str(evt1.get("place")))
    raw2 = normalize_token(safe_str(evt2.get("place")))
    if not raw1 and not raw2:
        return 0.0
    return jaro_ratio(raw1, raw2)


def event_similarity(p1: Dict[str, Any], p2: Dict[str, Any]) -> float:
    """
    Very lightweight event similarity:
      - Compare set of event tags (BIRT/DEAT/MARR/etc.)
      - Score = |intersection| / |union|
    """
    ev1 = p1.get("events", [])
    ev2 = p2.get("events", [])

    tags1 = {safe_str(e.get("tag")).upper() for e in ev1 if isinstance(e, dict)}
    tags2 = {safe_str(e.get("tag")).upper() for e in ev2 if isinstance(e, dict)}

    if not tags1 or not tags2:
        return 0.0

    inter = tags1 & tags2
    union = tags1 | tags2
    if not union:
        return 0.0

    return len(inter) / len(union)


def compute_individual_similarity(
    p1: Dict[str, Any],
    p2: Dict[str, Any],
) -> Tuple[float, Dict[str, float]]:
    """
    Compare two individuals and return (score, details dict).
    """
    sims = {}
    sims["name"] = name_similarity(p1, p2)
    sims["birth"] = birth_similarity(p1, p2)
    sims["place"] = place_similarity(p1, p2)
    sims["events"] = event_similarity(p1, p2)

    # Weighted combination; you can tune these later.
    score = (
        0.40 * sims["name"] +
        0.30 * sims["birth"] +
        0.20 * sims["place"] +
        0.10 * sims["events"]
    )

    return score, sims


# ---------------------------------------------------------------------------
# Candidate generation: Individuals
# ---------------------------------------------------------------------------

def collect_individual_candidates(
    registry: Dict[str, Any],
    min_score: float,
    max_pairs: int,
) -> List[Dict[str, Any]]:
    """Generate and score candidate duplicate individuals."""
    individuals = registry.get("individuals", {})
    log.info(
        "collect_individual_candidates: individuals=%d, min_score=%.3f, max_pairs=%d",
        len(individuals), min_score, max_pairs,
    )

    blocks = build_individual_blocks(individuals)
    pairs = generate_block_pairs(blocks, max_pairs)
    candidates: List[Dict[str, Any]] = []

    for a, b in pairs:
        pa = individuals.get(a)
        pb = individuals.get(b)
        if not isinstance(pa, dict) or not isinstance(pb, dict):
            continue
        score, details = compute_individual_similarity(pa, pb)
        if score >= min_score:
            candidates.append(
                {
                    "id1": a,
                    "id2": b,
                    "score": score,
                    "details": details,
                }
            )

    log.info(
        "Individual candidate collection complete: total_pairs_considered=%d, kept=%d (score>=%.3f)",
        len(pairs), len(candidates), min_score,
    )
    return candidates


# ---------------------------------------------------------------------------
# Skeleton candidate generators for families & events
# ---------------------------------------------------------------------------

def collect_family_candidates(
    registry: Dict[str, Any],
    min_score: float,
    max_pairs: int,
) -> List[Dict[str, Any]]:
    """
    FAMILY candidate generation (skeleton).
    For now, returns an empty list; we will implement later.
    """
    families = registry.get("families", {})
    log.info(
        "collect_family_candidates (skeleton): families=%d, min_score=%.3f, max_pairs=%d",
        len(families), min_score, max_pairs,
    )
    return []


def collect_event_candidates(
    registry: Dict[str, Any],
    min_score: float,
    max_pairs: int,
) -> List[Dict[str, Any]]:
    """
    EVENT candidate generation (skeleton).
    For now, returns an empty list; we will implement later.
    """
    # A simple count of events for logging:
    individuals = registry.get("individuals", {})
    events_count = 0
    for p in individuals.values():
        if isinstance(p, dict):
            evts = p.get("events", [])
            if isinstance(evts, list):
                events_count += len(evts)

    log.info(
        "collect_event_candidates (skeleton): events=%d, min_score=%.3f, max_pairs=%d",
        events_count, min_score, max_pairs,
    )
    return []


# ---------------------------------------------------------------------------
# Clustering (connected components from candidate edges)
# ---------------------------------------------------------------------------

def build_clusters(candidates: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """Turn candidate pairs into connected clusters: cid -> [ids]."""
    graph: Dict[str, set] = {}

    for c in candidates:
        a = c.get("id1")
        b = c.get("id2")
        if not a or not b:
            continue
        graph.setdefault(a, set()).add(b)
        graph.setdefault(b, set()).add(a)

    visited: set = set()
    clusters: Dict[str, List[str]] = {}
    cid_counter = 1

    for node in graph:
        if node not in visited:
            cluster_nodes = _dfs_collect(node, graph, visited)
            cid = f"C{cid_counter}"
            clusters[cid] = sorted(cluster_nodes)
            cid_counter += 1

    log.debug("Clustered %d nodes into %d clusters", len(graph), len(clusters))
    return clusters


def _dfs_collect(start: str, graph: Dict[str, set], visited: set) -> List[str]:
    stack = [start]
    out: List[str] = []
    while stack:
        n = stack.pop()
        if n not in visited:
            visited.add(n)
            out.append(n)
            stack.extend(graph.get(n, []))
    return out


# ---------------------------------------------------------------------------
# Merge decision logic
# ---------------------------------------------------------------------------

def build_merge_plan(
    clusters: Dict[str, List[str]],
    candidates: List[Dict[str, Any]],
    auto_merge_threshold: float,
    review_threshold: float,
) -> Dict[str, Dict[str, Any]]:
    """Return merge plan: cluster_id → merge instructions."""
    plan: Dict[str, Dict[str, Any]] = {}

    # Map for quick score lookup
    score_map: Dict[str, float] = {}
    for c in candidates:
        a = c.get("id1")
        b = c.get("id2")
        s = float(c.get("score", 0.0))
        if not a or not b:
            continue
        score_map[f"{a}|{b}"] = s
        score_map[f"{b}|{a}"] = s

    for cid, members in clusters.items():
        decision = decide_cluster_merge(
            cid,
            members,
            score_map,
            auto_merge_threshold,
            review_threshold,
        )
        plan[cid] = decision

    return plan


def decide_cluster_merge(
    cid: str,
    members: List[str],
    score_map: Dict[str, float],
    auto_thresh: float,
    review_thresh: float,
) -> Dict[str, Any]:

    if len(members) == 1:
        return {"cid": cid, "action": "no_merge", "members": members}

    pair_scores: List[float] = []
    for i in range(len(members)):
        for j in range(i + 1, len(members)):
            key = f"{members[i]}|{members[j]}"
            pair_scores.append(score_map.get(key, 0.0))

    if not pair_scores:
        return {"cid": cid, "action": "no_merge", "members": members}

    min_s = min(pair_scores)
    max_s = max(pair_scores)

    if min_s >= auto_thresh:
        action = "auto_merge"
    elif min_s >= review_thresh:
        action = "review"
    else:
        action = "no_merge"

    return {
        "cid": cid,
        "action": action,
        "members": members,
        "min_score": min_s,
        "max_score": max_s,
        "pair_scores": pair_scores,
    }


# ---------------------------------------------------------------------------
# Applying merges to the registry
# ---------------------------------------------------------------------------

def apply_merges_to_registry(
    registry: Dict[str, Any],
    merge_plan: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Apply auto-merges to the registry, retain originals for review/no_merge.
    - For now, we:
        * auto_merge → create a new unified individual U<CID>
        * review/no_merge → keep originals
    - We also rewrite families using the resulting ID map.
    """
    individuals = registry.get("individuals", {})
    new_individuals: Dict[str, Any] = {}

    id_map: Dict[str, str] = {}

    for cid, info in merge_plan.items():
        members = info.get("members", [])
        action = info.get("action", "no_merge")

        if action == "auto_merge" and len(members) >= 2:
            new_id = f"U{cid}"
            unified = merge_individual_group(new_id, members, individuals)
            new_individuals[new_id] = unified
            for m in members:
                id_map[m] = new_id
        else:
            # no_merge or review → keep them as-is
            for m in members:
                if m not in new_individuals and m in individuals:
                    new_individuals[m] = individuals[m]
                id_map.setdefault(m, m)

    # Rewrite families via id_map
    new_families = rewrite_families(registry.get("families", {}), id_map)

    out = dict(registry)
    out["individuals"] = new_individuals
    out["families"] = new_families
    out["id_map"] = id_map
    return out


def merge_individual_group(
    new_id: str,
    members: List[str],
    individuals: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Merge multiple individuals into one unified record.
    This is intentionally conservative and additive.
    """
    merged: Dict[str, Any] = {
        "id": new_id,
        "source_ids": members,
        "names": [],
        "events": [],
        "gender": None,
    }

    for mid in members:
        p = individuals.get(mid)
        if not isinstance(p, dict):
            continue

        # Merge names
        if "names" in p and isinstance(p["names"], list):
            merged["names"].extend(p["names"])

        # Merge events
        if "events" in p and isinstance(p["events"], list):
            merged["events"].extend(p["events"])

        # Set gender once if not already set
        if merged["gender"] is None and p.get("gender") is not None:
            merged["gender"] = p.get("gender")

    return merged


def rewrite_families(
    families: Dict[str, Any],
    id_map: Dict[str, str],
) -> Dict[str, Any]:
    """
    Rewrite FAM records to use merged individual IDs.
    """
    new_fams: Dict[str, Any] = {}

    for fid, fam in families.items():
        if not isinstance(fam, dict):
            new_fams[fid] = fam
            continue

        f2 = dict(fam)

        # Husband / Wife
        if "husband" in f2:
            f2["husband"] = id_map.get(f2["husband"], f2["husband"])
        if "wife" in f2:
            f2["wife"] = id_map.get(f2["wife"], f2["wife"])

        # Children
        if "children" in f2 and isinstance(f2["children"], list):
            f2["children"] = [id_map.get(c, c) for c in f2["children"]]

        new_fams[fid] = f2

    return new_fams


# ---------------------------------------------------------------------------
# IO helpers
# ---------------------------------------------------------------------------

def load_registry(path: str) -> Dict[str, Any]:
    log.debug("Loading registry: %s", path)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_candidates(path: str, data: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    log.info("Entity candidates written to: %s", path)


def write_summary(
    path: str,
    old_reg: Dict[str, Any],
    new_reg: Dict[str, Any],
    clusters: Dict[str, List[str]],
    merge_plan: Dict[str, Any],
) -> None:
    summary = {
        "individuals_in": len(old_reg.get("individuals", {})),
        "individuals_out": len(new_reg.get("individuals", {})),
        "clusters_total": len(clusters),
        "auto_merged": sum(1 for v in merge_plan.values() if v.get("action") == "auto_merge"),
        "review": sum(1 for v in merge_plan.values() if v.get("action") == "review"),
        "no_merge": sum(1 for v in merge_plan.values() if v.get("action") == "no_merge"),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    log.info("Entity resolution summary written to: %s", path)


def write_registry(path: str, registry: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2)
    log.info("Writing enriched registry to: %s", path)


# ---------------------------------------------------------------------------
# CLI / Main
# ---------------------------------------------------------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="C.24.4.10 – Entity Resolution")
    parser.add_argument("input", help="Input JSON from event_scoring (export_scored.json)")
    parser.add_argument("-o", "--output", required=True,
                        help="Output: export_entities_resolved.json")
    parser.add_argument("--candidates", required=True,
                        help="Output candidate pairs (JSON)")
    parser.add_argument("--summary", required=True,
                        help="Output summary (JSON)")
    parser.add_argument("--min-score", type=float, default=DEFAULT_MIN_SCORE)
    parser.add_argument("--auto-merge-threshold", type=float,
                        default=DEFAULT_AUTO_MERGE_THRESHOLD)
    parser.add_argument("--review-threshold", type=float,
                        default=DEFAULT_REVIEW_THRESHOLD)
    parser.add_argument("--max-pairs", type=int, default=DEFAULT_MAX_PAIRS)
    parser.add_argument("--debug", action="store_true")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    if args.debug:
        log.setLevel(logging.DEBUG)

    log.info(
        "Entity resolution starting. Input=%s, candidates=%s, summary=%s",
        args.input, args.candidates, args.summary,
    )

    registry = load_registry(args.input)

    # 1) Collect candidates
    indiv_candidates = collect_individual_candidates(
        registry,
        min_score=args.min_score,
        max_pairs=args.max_pairs,
    )

    fam_candidates = collect_family_candidates(
        registry,
        min_score=args.min_score,
        max_pairs=args.max_pairs,
    )

    evt_candidates = collect_event_candidates(
        registry,
        min_score=args.min_score,
        max_pairs=args.max_pairs,
    )

    all_candidates = {
        "individuals": indiv_candidates,
        "families": fam_candidates,
        "events": evt_candidates,
    }

    # 2) Build clusters and merge plan (for individuals)
    clusters = build_clusters(indiv_candidates)
    merge_plan = build_merge_plan(
        clusters,
        indiv_candidates,
        auto_merge_threshold=args.auto_merge_threshold,
        review_threshold=args.review_threshold,
    )

    # 3) Apply merges to registry
    new_registry = apply_merges_to_registry(registry, merge_plan)

    # 4) Write outputs
    write_candidates(args.candidates, all_candidates)
    write_summary(args.summary, registry, new_registry, clusters, merge_plan)
    write_registry(args.output, new_registry)

    log.info("Entity resolution complete.")


if __name__ == "__main__":
    main()
