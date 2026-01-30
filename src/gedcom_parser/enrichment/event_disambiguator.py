"""
C.24.4.8 – Event Disambiguation & Scoring (Modern Export Compatible)

Works on modern exports where:
  - root is a dict
  - records live under keys like "individuals", "families", etc.
  - record["events"] is typically a LIST of event dicts

If an event dict contains:
  - "alternates": [ {event}, {event}, ... ]
Then we score [primary] + alternates, select a winner, and overwrite the
primary event dict in-place (preserving alternates + disambiguation containers).

This module intentionally does NOT depend on registry initialization.
"""

from __future__ import annotations

import argparse
import json
from typing import Any, Dict, Iterable, List, Optional

from gedcom_parser.logger import get_logger

log = get_logger("event_disambiguator")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_place_raw(ev: Dict[str, Any]) -> str:
    """Best-effort extraction of raw place text from an event block."""
    place = ev.get("place")
    if isinstance(place, dict):
        raw = place.get("raw") or place.get("normalized")
        if raw:
            return str(raw)

    # Legacy-ish fallbacks
    if ev.get("place_raw"):
        return str(ev["place_raw"])
    if ev.get("value"):
        return str(ev["value"])
    return ""


def _score_event(ev: Any) -> int:
    """Heuristic scoring function for choosing a primary event."""
    if not isinstance(ev, dict):
        return 0

    score = 0

    # 1) Date quality
    raw_date = (ev.get("date") or "").strip()
    if raw_date:
        score += 50
        upper = raw_date.upper()
        if any(q in upper for q in ("ABT", "BEF", "AFT", "EST", "CALC")):
            score -= 10
        if any(sep in raw_date for sep in (" ", "/", "-")):
            score += 5

    # 2) Place quality
    place = ev.get("place")
    if isinstance(place, dict) and (place.get("raw") or place.get("parts") or place.get("normalized")):
        score += 30
        parts = place.get("parts") or {}
        non_empty_parts = [v for v in parts.values() if v]
        if len(non_empty_parts) >= 2:
            score += 5
        coords = place.get("coordinates") or {}
        if coords.get("lat") is not None and coords.get("lon") is not None:
            score += 5
    else:
        if _safe_place_raw(ev):
            score += 10

    # 3) Sources
    sources = ev.get("sources") or []
    if isinstance(sources, list):
        if len(sources) >= 1:
            score += 5
        if len(sources) >= 3:
            score += 5

    # 4) Notes
    notes = ev.get("notes") or []
    if isinstance(notes, list) and notes:
        score += 3

    # 5) slight bump if already explicitly non-ambiguous
    if ev.get("ambiguous") is False:
        score += 2

    return score


def _copy_event_fields(dst: Dict[str, Any], src: Dict[str, Any]) -> None:
    """
    In-place overwrite of dst with src's data,
    preserving the 'alternates' and 'disambiguation' containers.
    """
    preserve = {"alternates", "disambiguation"}

    for key in list(dst.keys()):
        if key not in preserve:
            dst.pop(key, None)

    for key, value in src.items():
        if key in preserve:
            continue
        dst[key] = value


def _iter_record_dicts(root: Any) -> Iterable[Dict[str, Any]]:
    """
    Yield any dict that looks like a record (has an 'events' key).
    This is intentionally schema-agnostic.
    """
    if isinstance(root, dict):
        if "events" in root:
            yield root
        for v in root.values():
            yield from _iter_record_dicts(v)
    elif isinstance(root, list):
        for item in root:
            yield from _iter_record_dicts(item)


# ---------------------------------------------------------------------------
# Core disambiguation
# ---------------------------------------------------------------------------

def disambiguate_events_tree(root: Dict[str, Any], debug_enabled: bool = False) -> Dict[str, Any]:
    total_records = 0
    total_events = 0
    with_alts = 0
    resolved = 0
    ties = 0
    remaining_ambiguous = 0

    for rec in _iter_record_dicts(root):
        events = rec.get("events")

        # Modern: events is a LIST
        if isinstance(events, list):
            total_records += 1
            rec_id = rec.get("uuid") or rec.get("pointer") or "<??>"

            for ev in events:
                total_events += 1
                if not isinstance(ev, dict):
                    continue

                alts = ev.get("alternates") or []
                if not isinstance(alts, list) or not alts:
                    continue

                with_alts += 1
                candidates: List[Dict[str, Any]] = [ev] + [a for a in alts if isinstance(a, dict)]
                scores: List[int] = []

                for idx, cand in enumerate(candidates):
                    sc = _score_event(cand)
                    scores.append(sc)
                    cand.setdefault("disambiguation", {})
                    cand["disambiguation"]["score"] = sc

                    if debug_enabled:
                        log.debug("Record %s candidate #%d score=%d", rec_id, idx, sc)

                if not scores:
                    continue

                max_score = max(scores)
                winners = [i for i, sc in enumerate(scores) if sc == max_score]

                if len(winners) > 1:
                    ties += 1
                    ev["ambiguous"] = True
                    ev.setdefault("disambiguation", {})["tie"] = True
                    remaining_ambiguous += 1
                    continue

                winner_idx = winners[0]
                winner = candidates[winner_idx]

                _copy_event_fields(ev, winner)
                ev["ambiguous"] = False

                # rebuild alternates (no self-reference)
                if winner_idx == 0:
                    loser_list = list(alts)
                else:
                    loser_list = [a for i, a in enumerate(alts) if (i + 1) != winner_idx]

                ev["alternates"] = loser_list
                ev.setdefault("disambiguation", {})["winner_index"] = winner_idx
                resolved += 1

            continue

        # Legacy fallback: events is a DICT (keep compatibility if encountered)
        if isinstance(events, dict):
            total_records += 1
            rec_id = rec.get("uuid") or rec.get("pointer") or "<??>"

            for tag, primary in events.items():
                total_events += 1
                if not isinstance(primary, dict):
                    continue

                alts = primary.get("alternates") or []
                if not isinstance(alts, list) or not alts:
                    continue

                with_alts += 1
                candidates = [primary] + [a for a in alts if isinstance(a, dict)]
                scores = []
                for idx, cand in enumerate(candidates):
                    sc = _score_event(cand)
                    scores.append(sc)
                    cand.setdefault("disambiguation", {})
                    cand["disambiguation"]["score"] = sc
                    if debug_enabled:
                        log.debug("Record %s tag=%s candidate #%d score=%d", rec_id, tag, idx, sc)

                if not scores:
                    continue

                max_score = max(scores)
                winners = [i for i, sc in enumerate(scores) if sc == max_score]

                if len(winners) > 1:
                    ties += 1
                    primary["ambiguous"] = True
                    primary.setdefault("disambiguation", {})["tie"] = True
                    remaining_ambiguous += 1
                    continue

                winner_idx = winners[0]
                winner = candidates[winner_idx]
                _copy_event_fields(primary, winner)
                primary["ambiguous"] = False

                if winner_idx == 0:
                    loser_list = list(alts)
                else:
                    loser_list = [a for i, a in enumerate(alts) if (i + 1) != winner_idx]

                primary["alternates"] = loser_list
                primary.setdefault("disambiguation", {})["winner_index"] = winner_idx
                resolved += 1

    log.info(
        "Event disambiguation: records=%d, events=%d, with_alts=%d, "
        "resolved=%d, ties=%d, remaining_ambiguous=%d",
        total_records,
        total_events,
        with_alts,
        resolved,
        ties,
        remaining_ambiguous,
    )
    return root


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        description="C.24.4.8 – GEDCOM event disambiguation based on scoring (modern export compatible)."
    )
    parser.add_argument("input", help="Input JSON file (from place_standardizer).")
    parser.add_argument(
        "-o",
        "--output",
        default="outputs/export_events_resolved.json",
        help="Output JSON file (default: outputs/export_events_resolved.json)",
    )
    parser.add_argument("--debug", action="store_true", help="Enable verbose debugging.")
    args = parser.parse_args(argv)

    debug_enabled = bool(args.debug)

    log.info("Loading input JSON: %s", args.input)
    with open(args.input, "r", encoding="utf-8") as f:
        root = json.load(f)

    updated = disambiguate_events_tree(root, debug_enabled=debug_enabled)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(updated, f, ensure_ascii=False, indent=2)

    log.info("Event disambiguation complete. Output written to: %s", args.output)


if __name__ == "__main__":
    main()
