"""
C.24.4.8 – Event Disambiguation & Scoring

Goal
----
For each record that has an "events" dict (typically INDI/FAM):

- Look at the primary event and any `.alternates`.
- Compute a heuristic score per candidate using:
    * date presence / quality
    * place presence / granularity / coordinates
    * attached sources / notes
- Pick a single "primary" winner whenever possible.
- Preserve ALL alternates, but clearly mark which one was chosen
  and why (or mark as a true tie).

Runs AFTER:
  - main export
  - xref_resolver
  - place_standardizer

We do *in-place* updates to the JSON tree and write it back out.
"""

from __future__ import annotations

import argparse
import json
from typing import Any, Dict, List

from gedcom_parser.logging import get_logger
from gedcom_parser.registry import get_registry

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_place_raw(ev: Dict[str, Any]) -> str:
    """Best-effort extraction of raw place text from an event block."""
    place = ev.get("place")
    if isinstance(place, dict):
        raw = place.get("raw")
        if raw:
            return str(raw)

    # Legacy fallbacks if the structure isn't standardized yet
    if ev.get("place_raw"):
        return str(ev["place_raw"])
    if ev.get("value"):
        return str(ev["value"])
    return ""


def _score_event(ev: Dict[str, Any]) -> int:
    """
    Heuristic scoring function for choosing a primary event.

    Rough weighting:
      - Date presence / quality dominates.
      - Place granularity & coordinates next.
      - Sources & notes as tie-breakers.
    """
    if not isinstance(ev, dict):
        return 0

    score = 0

    # 1) Date quality
    raw_date = (ev.get("date") or "").strip()
    if raw_date:
        score += 50
        upper = raw_date.upper()
        # Penalize fuzzy dates
        if any(q in upper for q in ("ABT", "BEF", "AFT", "EST", "CALC")):
            score -= 10
        # Reward more "structured" dates
        if any(sep in raw_date for sep in (" ", "/", "-")):
            score += 5

    # 2) Place quality
    place = ev.get("place") or {}
    if isinstance(place, dict) and (place.get("raw") or place.get("parts")):
        score += 30
        parts = place.get("parts") or {}
        # Good if we have at least 2+ structured parts
        non_empty_parts = [v for v in parts.values() if v]
        if len(non_empty_parts) >= 2:
            score += 5
        coords = place.get("coordinates") or {}
        if coords.get("lat") is not None and coords.get("lon") is not None:
            score += 5
    else:
        # Fallback to any raw place text
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
    if isinstance(notes, list) and len(notes) > 0:
        score += 3

    # 5) Slight bump if explicitly marked non-ambiguous
    if ev.get("ambiguous") is False:
        score += 2

    return score


def _copy_event_fields(dst: Dict[str, Any], src: Dict[str, Any]) -> None:
    """
    In-place overwrite of dst (the primary event slot) with src's data,
    preserving the 'alternates' and 'disambiguation' containers.
    """
    preserve = {"alternates", "disambiguation"}

    # Clear everything but preserved keys
    for key in list(dst.keys()):
        if key not in preserve:
            dst.pop(key, None)

    # Copy new content in
    for key, value in src.items():
        if key in preserve:
            continue
        dst[key] = value


def _iter_records_with_events(node: Any):
    """
    Generic tree walk: yield any dict that has an 'events' key which looks
    like our events mapping. This makes the disambiguator agnostic to the
    exact nesting of INDI/FAM/etc.
    """
    if isinstance(node, dict):
        if isinstance(node.get("events"), dict):
            yield node
        for val in node.values():
            yield from _iter_records_with_events(val)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_records_with_events(item)


# ---------------------------------------------------------------------------
# Core disambiguation
# ---------------------------------------------------------------------------

def disambiguate_events_tree(
    root: Dict[str, Any],
    debug_enabled: bool = False,
) -> Dict[str, Any]:
    """
    Walk the entire JSON tree, disambiguate all events that have alternates,
    and return the modified root.
    """
    total_records = 0
    total_events = 0
    with_alts = 0
    resolved = 0
    ties = 0
    remaining_ambiguous = 0

    for rec in _iter_records_with_events(root):
        total_records += 1
        rec_id = rec.get("uuid") or rec.get("pointer") or "<??>"
        events = rec.get("events") or {}

        for tag, primary in events.items():
            total_events += 1

            if not isinstance(primary, dict):
                continue

            alts = primary.get("alternates") or []
            if not alts:
                # Nothing to disambiguate
                continue

            with_alts += 1
            candidates: List[Dict[str, Any]] = [primary] + list(alts)
            scores: List[int] = []

            # Score each candidate
            for idx, ev in enumerate(candidates):
                sc = _score_event(ev)
                scores.append(sc)

                ev.setdefault("disambiguation", {})
                ev["disambiguation"]["score"] = sc

                if debug_enabled:
                    log.debug(
                        "Record %s tag=%s candidate #%d score=%d",
                        rec_id,
                        tag,
                        idx,
                        sc,
                    )

            max_score = max(scores)
            winners = [i for i, sc in enumerate(scores) if sc == max_score]

            if len(winners) > 1:
                # Tie: leave ambiguous; do NOT alter alternates
                ties += 1
                primary["ambiguous"] = True
                primary.setdefault("disambiguation", {})["tie"] = True
                remaining_ambiguous += 1

                if debug_enabled:
                    log.debug(
                        "Record %s tag=%s remains ambiguous (tie among %s, score=%d)",
                        rec_id,
                        tag,
                        winners,
                        max_score,
                    )
                continue

            # Unique winner
            winner_idx = winners[0]
            winner = candidates[winner_idx]

            # Overwrite primary slot with winner's data
            _copy_event_fields(primary, winner)
            primary["ambiguous"] = False

            # Build a safe alternates list WITHOUT self-reference
            if winner_idx == 0:
                # Original primary wins – all alts remain as alternates
                loser_list = list(alts)
            else:
                # One of the alternates wins – alternates = all other alternates
                # (we do NOT include the primary container itself to avoid cycles)
                loser_list = [
                    ev for i, ev in enumerate(alts) if (i + 1) != winner_idx
                ]

            primary["alternates"] = loser_list
            primary.setdefault("disambiguation", {})["winner_index"] = winner_idx
            resolved += 1

            if debug_enabled:
                log.debug(
                    "Record %s tag=%s resolved to candidate #%d (score=%d)",
                    rec_id,
                    tag,
                    winner_idx,
                    max_score,
                )

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

def main(argv: List[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="C.24.4.8 – GEDCOM event disambiguation based on scoring."
    )
    parser.add_argument(
        "input",
        help="Input JSON file (from place_standardizer).",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="outputs/export_events_resolved.json",
        help="Output JSON file (default: outputs/export_events_resolved.json)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Request verbose debugging (requires debug:true in config/gedcom_parser.yml).",
    )

    args = parser.parse_args(argv)

    # Ensure config + registry are instantiated (also configures logging).
    reg = get_registry()
    cfg = reg.config
    debug_enabled = bool(args.debug and cfg.debug)

    if args.debug and not cfg.debug:
        log.warning(
            "--debug flag passed but config.debug is False; "
            "set debug: true in config/gedcom_parser.yml to see debug lines."
        )

    log.info("Loading input JSON: %s", args.input)
    with open(args.input, "r", encoding="utf-8") as f:
        root = json.load(f)

    updated = disambiguate_events_tree(root, debug_enabled=debug_enabled)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(updated, f, ensure_ascii=False, indent=2)

    log.info("Event disambiguation complete. Output written to: %s", args.output)


if __name__ == "__main__":
    main()
