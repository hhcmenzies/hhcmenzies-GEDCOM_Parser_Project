"""
event_scoring.py — Phase C.24.4.9
Corrected version using your actual registry structure:

{
    "individuals": {...},
    "families": {...},
    "sources": {...},
    "repositories": {...},
    "media_objects": {...}
}
"""

import argparse
import json
from typing import Any, Dict, List, Tuple, Optional

# Try to use project logger, else fallback to print/logging
try:
    from gedcom_parser.logging import get_logger
    from gedcom_parser.config import get_config
except Exception:  # fallback
    import logging
    def get_logger(name: str):
        logging.basicConfig(level=logging.INFO)
        return logging.getLogger(name)
    def get_config():
        class Cfg:
            debug = False
        return Cfg()

log = get_logger("event_scoring")

# ======================================================================
# CLI ENTRY POINT
# ======================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="GEDCOM Event Scoring Engine (C.24.4.9)"
    )

    parser.add_argument("input", help="Input JSON file (export_events_resolved.json)")
    parser.add_argument(
        "-o",
        "--output",
        required=True,
        help="Output JSON with scoring (export_scored.json)",
    )
    parser.add_argument("--event-scores", help="Flattened scoring file")
    parser.add_argument("--summary", help="Summary scoring file")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    cfg = get_config()
    if args.debug and hasattr(cfg, "debug"):
        cfg.debug = True

    # Set logger to DEBUG if needed
    if args.debug:
        try:
            import logging
            log.setLevel(logging.DEBUG)
        except Exception:
            pass

    print(f"[event_scoring] Starting scoring. Input={args.input}, Output={args.output}")
    log.info("Event scoring starting. Input=%s, Output=%s", args.input, args.output)

    registry = _load_json(args.input)

    scored_registry, flat_scores, summary = score_registry(registry)

    _write_json(args.output, scored_registry)
    print(f"[event_scoring] Scored registry written to: {args.output}")
    log.info("Scored registry written to: %s", args.output)

    if args.event_scores:
        _write_json(args.event_scores, flat_scores)
        print(f"[event_scoring] Flattened scores written to: {args.event_scores}")
        log.info("Flattened event scores written to: %s", args.event_scores)

    if args.summary:
        _write_json(args.summary, summary)
        print(f"[event_scoring] Summary written to: {args.summary}")
        log.info("Scoring summary written to: %s", args.summary)

    print("[event_scoring] Done.")
    log.info("Event scoring complete.")


# ======================================================================
# JSON LOAD / SAVE
# ======================================================================

def _load_json(path: str) -> Dict[str, Any]:
    log.debug("Loading JSON: %s", path)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: str, obj: Any) -> None:
    log.debug("Writing JSON: %s", path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


# ======================================================================
# SCORING REGISTRY
# ======================================================================

def score_registry(registry: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any]]:
    """
    Score all individuals and events using your ACTUAL registry structure:

    {
        "individuals": {...},
        "families": {...},
        "sources": {...},
        "repositories": {...},
        "media_objects": {...}
    }
    """

    individuals = registry.get("individuals", {}) or {}

    flat_scores: List[Dict[str, Any]] = []

    individuals_scored = 0
    events_scored = 0
    low_conf = 0
    conflicts = 0
    hybrid_sum = 0.0

    for indi_id, person in individuals.items():
        individuals_scored += 1

        events_obj = person.get("events") or {}
        # events can be a dict of tag->event or a list of event dicts
        if isinstance(events_obj, dict):
            event_list = list(events_obj.values())
        elif isinstance(events_obj, list):
            event_list = events_obj
        else:
            event_list = []

        person_scores: List[int] = []

        for event in event_list:
            if not isinstance(event, dict):
                # Defensive: skip if not a dict
                log.debug("Skipping non-dict event for individual %s: %r", indi_id, event)
                continue

            score_block, flags = score_single_event(event, person, registry)

            event["score"] = score_block

            flat_scores.append({
                "individual_id": indi_id,
                "individual_uuid": person.get("uuid"),
                "event_uuid": event.get("uuid"),
                "event_tag": event.get("tag"),
                "hybrid": score_block["hybrid"],
                "completeness": score_block["completeness"],
                "consistency": score_block["consistency"],
                "evidence": score_block["evidence"],
                "ranking": score_block["ranking"],
                "flags": score_block["flags"],
            })

            events_scored += 1
            hybrid_sum += score_block["hybrid"]
            person_scores.append(score_block["hybrid"])

            if score_block["hybrid"] < 40:
                low_conf += 1
            if "conflicts_with_other_events" in flags:
                conflicts += 1

        # Per-individual summary
        if person_scores:
            person["scoring"] = {
                "events_scored": len(person_scores),
                "avg_event_score": sum(person_scores) / len(person_scores),
                "min_event_score": min(person_scores),
                "max_event_score": max(person_scores),
                "low_confidence_events": sum(1 for s in person_scores if s < 40),
            }

    avg_event_score = (hybrid_sum / events_scored) if events_scored else 0.0

    summary = {
        "individuals_scored": individuals_scored,
        "events_scored": events_scored,
        "low_confidence_events": low_conf,
        "conflicting_events": conflicts,
        "average_event_score": avg_event_score,
        "scoring_version": "C.24.4.9",
    }

    log.info(
        "Scoring summary: individuals=%d, events=%d, low_conf=%d, conflicts=%d, avg=%.2f",
        individuals_scored, events_scored, low_conf, conflicts, avg_event_score
    )

    return registry, flat_scores, summary


# ======================================================================
# EVENT SCORING
# ======================================================================

def score_single_event(
    event: Dict[str, Any],
    person: Dict[str, Any],
    registry: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[str]]:
    flags: List[str] = []

    A = score_deterministic(event, person, flags)
    C = score_cross_evidence(event, person, registry, flags)
    E = score_evidence(event, flags)

    hybrid = compute_hybrid(A, C, E)
    ranking = determine_ranking(event, hybrid, flags)

    score_block = {
        "completeness": A,
        "consistency": C,
        "evidence": E,
        "hybrid": hybrid,
        "ranking": ranking,
        "flags": flags,
        "version": "C.24.4.9",
    }

    log.debug(
        "Scored event tag=%s uuid=%s hybrid=%d (A=%d, C=%d, E=%d) flags=%s",
        event.get("tag"),
        event.get("uuid"),
        hybrid,
        A,
        C,
        E,
        flags,
    )

    return score_block, flags


# ======================================================================
# A — DETERMINISTIC SCORING
# ======================================================================

_date_cache: Dict[str, Tuple[Optional[int], Optional[int], Optional[int], int]] = {}


def parse_gedcom_date(date_str: str) -> Tuple[Optional[int], Optional[int], Optional[int], int]:
    if not date_str:
        return None, None, None, 0

    if date_str in _date_cache:
        return _date_cache[date_str]

    s = str(date_str).strip()
    parts = s.split()

    year = month = day = None
    precision = 0

    try:
        if len(parts) == 1:
            year = int(parts[0])
            precision = 1
        elif len(parts) == 2:
            mon, yr = parts
            year = int(yr)
            month = _month_to_int(mon)
            if month:
                precision = 2
        elif len(parts) == 3:
            d, mon, yr = parts
            day = int(d)
            year = int(yr)
            month = _month_to_int(mon)
            if month:
                precision = 3
    except Exception:
        precision = 0

    result = (year, month, day, precision)
    _date_cache[date_str] = result
    return result


def _month_to_int(mon: str) -> Optional[int]:
    m = mon.upper()
    months = {
        "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
        "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
    }
    return months.get(m)


def score_deterministic(event: Dict[str, Any], person: Dict[str, Any], flags: List[str]) -> int:
    score = 0
    score += score_date_precision(event, flags)
    score += score_place_precision(event, flags)
    score += score_field_completeness(event, flags)
    score += score_basic_consistency(event, person, flags)
    return max(0, min(100, score))


def score_date_precision(event: Dict[str, Any], flags: List[str]) -> int:
    v = event.get("date")
    if not v:
        flags.append("no_date")
        return 0
    _, _, _, precision = parse_gedcom_date(str(v))
    if precision == 3:
        return 25
    if precision == 2:
        flags.append("partial_date")
        return 18
    if precision == 1:
        flags.append("partial_date")
        return 10
    flags.append("unrecognized_date_format")
    return 5


def score_place_precision(event: Dict[str, Any], flags: List[str]) -> int:
    place = event.get("place")
    if not place:
        flags.append("no_place")
        return 0

    depth = 0
    if isinstance(place, dict):
        parts = place.get("parts")
        if isinstance(parts, dict):
            depth = len(parts)
        elif isinstance(parts, list):
            depth = len(parts)
        elif place.get("normalized"):
            depth = 2
    elif isinstance(place, str):
        depth = len([p for p in place.split(",") if p.strip()])

    if depth >= 4:
        return 25
    if depth == 3:
        return 20
    if depth == 2:
        return 15
    if depth == 1:
        return 10
    flags.append("ambiguous_place")
    return 5


def score_field_completeness(event: Dict[str, Any], flags: List[str]) -> int:
    score = 0
    if event.get("date"):
        score += 8
    if event.get("place"):
        score += 8

    sources = event.get("sources") or []
    if sources:
        score += 5
    else:
        flags.append("no_sources")

    extras = 0
    for key in ("age", "cause", "role", "description"):
        if event.get(key):
            extras += 1
    score += min(extras, 4)
    return min(25, score)


def score_basic_consistency(event: Dict[str, Any], person: Dict[str, Any], flags: List[str]) -> int:
    events_obj = person.get("events") or {}
    if isinstance(events_obj, dict):
        all_events = list(events_obj.values())
    elif isinstance(events_obj, list):
        all_events = events_obj
    else:
        all_events = []

    birth = None
    death = None

    for ev in all_events:
        if not isinstance(ev, dict):
            continue
        tag = ev.get("tag")
        if not ev.get("date"):
            continue
        dt = parse_gedcom_date(str(ev["date"]))
        if tag == "BIRT":
            birth = dt
        elif tag == "DEAT":
            death = dt

    score = 25
    if birth and death:
        by, _, _, _ = birth
        dy, _, _, _ = death
        if by and dy:
            if dy < by:
                flags.append("death_before_birth")
                flags.append("conflicts_with_other_events")
                score -= 15
            elif dy - by > 120:
                flags.append("unrealistic_lifespan")
                flags.append("conflicts_with_other_events")
                score -= 5

    return max(0, min(25, score))


# ======================================================================
# C — CROSS EVIDENCE
# ======================================================================

def score_cross_evidence(
    event: Dict[str, Any],
    person: Dict[str, Any],
    registry: Dict[str, Any],
    flags: List[str],
) -> int:
    alts = event.get("alternates") or event.get("alt_events") or []
    if not isinstance(alts, list):
        alts = []

    if not alts:
        return 100

    cluster = [event] + alts
    agreement = compute_cluster_agreement(cluster)
    conflict_penalty = compute_cluster_conflicts(cluster, flags)
    return max(0, min(100, agreement - conflict_penalty))


def compute_cluster_agreement(cluster: List[Dict[str, Any]]) -> int:
    if len(cluster) <= 1:
        return 100

    date_matches = 0
    date_pairs = 0
    place_matches = 0
    place_pairs = 0

    for i in range(len(cluster)):
        for j in range(i + 1, len(cluster)):
            e1 = cluster[i]
            e2 = cluster[j]

            d1 = e1.get("date")
            d2 = e2.get("date")
            if d1 or d2:
                date_pairs += 1
                if _dates_similar(d1, d2):
                    date_matches += 1

            p1 = e1.get("place")
            p2 = e2.get("place")
            if p1 or p2:
                place_pairs += 1
                if _places_similar(p1, p2):
                    place_matches += 1

    date_ratio = (date_matches / date_pairs) if date_pairs else 1.0
    place_ratio = (place_matches / place_pairs) if place_pairs else 1.0

    base_score = int(100 * (0.5 * date_ratio + 0.5 * place_ratio))
    return max(0, min(100, base_score))


def compute_cluster_conflicts(cluster: List[Dict[str, Any]], flags: List[str]) -> int:
    if len(cluster) <= 1:
        return 0

    severe_conflicts = 0

    for i in range(len(cluster)):
        for j in range(i + 1, len(cluster)):
            e1 = cluster[i]
            e2 = cluster[j]

            if _dates_strongly_conflict(e1.get("date"), e2.get("date")):
                severe_conflicts += 1
            if _places_strongly_conflict(e1.get("place"), e2.get("place")):
                severe_conflicts += 1

    if severe_conflicts:
        flags.append("conflicts_with_other_events")
    return min(100, severe_conflicts * 10)


def _dates_similar(d1: Any, d2: Any) -> bool:
    if not d1 or not d2:
        return False
    y1, m1, _, _ = parse_gedcom_date(str(d1))
    y2, m2, _, _ = parse_gedcom_date(str(d2))
    if not y1 or not y2:
        return False
    if y1 == y2:
        return True
    if abs(y1 - y2) == 1 and m1 and m2 and m1 == m2:
        return True
    return False


def _dates_strongly_conflict(d1: Any, d2: Any) -> bool:
    if not d1 or not d2:
        return False
    y1, _, _, _ = parse_gedcom_date(str(d1))
    y2, _, _, _ = parse_gedcom_date(str(d2))
    if not y1 or not y2:
        return False
    return abs(y1 - y2) >= 10


def _place_to_string(place: Any) -> str:
    if isinstance(place, str):
        return place
    if isinstance(place, dict):
        if place.get("normalized"):
            return str(place["normalized"])
        if place.get("original"):
            return str(place["original"])
        parts = place.get("parts")
        if isinstance(parts, dict):
            return ", ".join(str(v) for v in parts.values() if v)
        if isinstance(parts, list):
            return ", ".join(str(p) for p in parts if p)
    return ""


def _places_similar(p1: Any, p2: Any) -> bool:
    s1 = _place_to_string(p1).lower()
    s2 = _place_to_string(p2).lower()
    if not s1 or not s2:
        return False
    t1 = {t.strip() for t in s1.split(",") if t.strip()}
    t2 = {t.strip() for t in s2.split(",") if t.strip()}
    if not t1 or not t2:
        return False
    return not t1.isdisjoint(t2)


def _places_strongly_conflict(p1: Any, p2: Any) -> bool:
    s1 = _place_to_string(p1).lower()
    s2 = _place_to_string(p2).lower()
    if not s1 or not s2:
        return False
    t1 = {t.strip() for t in s1.split(",") if t.strip()}
    t2 = {t.strip() for t in s2.split(",") if t.strip()}
    if not t1 or not t2:
        return False
    return t1.isdisjoint(t2)


# ======================================================================
# EVIDENCE (E) + HYBRID
# ======================================================================

def score_evidence(event: Dict[str, Any], flags: List[str]) -> int:
    sources = event.get("sources") or []
    if not sources:
        if "no_sources" not in flags:
            flags.append("no_sources")
        return 10
    n = len(sources)
    if n >= 3:
        return 100
    if n == 2:
        return 60
    return 40


def compute_hybrid(A: int, C: int, E: int) -> int:
    val = 0.40 * A + 0.40 * C + 0.20 * E
    return max(0, min(100, int(round(val))))


def determine_ranking(event: Dict[str, Any], hybrid: int, flags: List[str]) -> str:
    if "alternate_event" in flags:
        if hybrid < 40:
            return "low_confidence"
        return "alternate"
    if hybrid >= 70:
        return "primary"
    if hybrid < 40:
        return "low_confidence"
    return "alternate"


# ======================================================================
# MODULE EXECUTION
# ======================================================================

if __name__ == "__main__":
    main()
