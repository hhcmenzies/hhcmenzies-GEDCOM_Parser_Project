"""
place_registry_builder.py

C.24.5 – Place Registry Promotion

Input : Registry JSON after place_standardizer (and any later stages).
Output: Same registry shape, plus a top-level `places` registry, and
        per-event `place_id` references where a standard_place exists.

Design goals
-----------
- Works directly on modern export JSON dicts (no dataclasses, no pydantic).
- Never deletes or restructures existing data.
- Adds:
    root["places"] = { place_id: PlaceRecord, ... }
    event["place_id"] = place_id
- Idempotent: safe to run multiple times.

PlaceRecord shape (minimal, forward-compatible)
----------------------------------------------
{
  "id": "<normalized-lowercase-id>",
  "normalized": "<cleaned string>",
  "raw_examples": ["<original string>", ...],   # limited sample list
  "counts": {
      "events": <int>,
      "individual_events": <int>,
      "family_events": <int>
  }
}

If later stages produce richer structured places (parts, coordinates, etc.),
this builder will preserve and extend them rather than overwrite.
"""

from __future__ import annotations

import argparse
import json
from typing import Any, Dict, List, Optional, Tuple

from gedcom_parser.logger import get_logger

log = get_logger("place_registry_builder")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _iter_events(container: Any) -> List[Dict[str, Any]]:
    """
    Return a mutable list of event dicts from a record container.
    The canonical export uses `events` as a list; if missing or not a list,
    return an empty list.
    """
    if not isinstance(container, dict):
        return []
    evs = container.get("events")
    if isinstance(evs, list):
        # Filter to dict events; leave non-dicts untouched elsewhere.
        return [e for e in evs if isinstance(e, dict)]
    return []


def _extract_standard_place(ev: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Best-effort extraction of standard_place.
    Accepts:
      - ev["standard_place"] dict from place_standardizer
      - future: ev["place"]["standard_place"] (if place becomes a dict)
    """
    std = ev.get("standard_place")
    if isinstance(std, dict) and std.get("id"):
        return std

    place = ev.get("place")
    if isinstance(place, dict):
        std2 = place.get("standard_place")
        if isinstance(std2, dict) and std2.get("id"):
            return std2

    return None


def _safe_append_unique(lst: List[str], value: str, max_len: int) -> None:
    if value in lst:
        return
    if len(lst) >= max_len:
        return
    lst.append(value)


def _ensure_place_record(
    places: Dict[str, Any],
    place_id: str,
    normalized: Optional[str],
    raw_example: Optional[str],
) -> Dict[str, Any]:
    """
    Ensure `places[place_id]` exists with the canonical minimal shape.
    Does not overwrite existing richer records.
    """
    rec = places.get(place_id)
    if not isinstance(rec, dict):
        rec = {"id": place_id}
        places[place_id] = rec

    # Normalize fields (only fill if missing)
    if normalized and not rec.get("normalized"):
        rec["normalized"] = normalized

    raw_examples = rec.get("raw_examples")
    if not isinstance(raw_examples, list):
        raw_examples = []
        rec["raw_examples"] = raw_examples
    if raw_example:
        _safe_append_unique(raw_examples, raw_example, max_len=10)

    counts = rec.get("counts")
    if not isinstance(counts, dict):
        counts = {"events": 0, "individual_events": 0, "family_events": 0}
        rec["counts"] = counts
    else:
        counts.setdefault("events", 0)
        counts.setdefault("individual_events", 0)
        counts.setdefault("family_events", 0)

    return rec


# ---------------------------------------------------------------------------
# Core builder
# ---------------------------------------------------------------------------

def promote_places_registry(root: Dict[str, Any]) -> Dict[str, int]:
    """
    Mutates `root` in-place (additive, idempotent).
    Returns metrics for logging/verification.
    """
    metrics: Dict[str, int] = {
        "places_created": 0,
        "places_seen": 0,
        "events_seen": 0,
        "events_linked": 0,
        "individuals_seen": 0,
        "families_seen": 0,
        "skipped_non_dict_events": 0,
    }

    if not isinstance(root, dict):
        return metrics

    places = root.get("places")
    if not isinstance(places, dict):
        places = {}
        root["places"] = places

    # Individuals
    individuals = root.get("individuals", {})
    if isinstance(individuals, dict):
        for _ptr, indi in individuals.items():
            if not isinstance(indi, dict):
                continue
            metrics["individuals_seen"] += 1
            evs_any = indi.get("events", [])
            if not isinstance(evs_any, list):
                continue

            for ev in evs_any:
                metrics["events_seen"] += 1
                if not isinstance(ev, dict):
                    metrics["skipped_non_dict_events"] += 1
                    continue

                std = _extract_standard_place(ev)
                if not std:
                    continue

                place_id = str(std.get("id"))
                metrics["places_seen"] += 1

                before = place_id in places
                rec = _ensure_place_record(
                    places,
                    place_id=place_id,
                    normalized=std.get("normalized"),
                    raw_example=std.get("raw"),
                )
                if not before:
                    metrics["places_created"] += 1

                # Increment counters
                rec["counts"]["events"] += 1
                rec["counts"]["individual_events"] += 1

                # Add per-event linkage (do not replace existing)
                if ev.get("place_id") != place_id:
                    ev["place_id"] = place_id
                    metrics["events_linked"] += 1

    # Families
    families = root.get("families", {})
    if isinstance(families, dict):
        for _ptr, fam in families.items():
            if not isinstance(fam, dict):
                continue
            metrics["families_seen"] += 1
            evs_any = fam.get("events", [])
            if not isinstance(evs_any, list):
                continue

            for ev in evs_any:
                metrics["events_seen"] += 1
                if not isinstance(ev, dict):
                    metrics["skipped_non_dict_events"] += 1
                    continue

                std = _extract_standard_place(ev)
                if not std:
                    continue

                place_id = str(std.get("id"))
                metrics["places_seen"] += 1

                before = place_id in places
                rec = _ensure_place_record(
                    places,
                    place_id=place_id,
                    normalized=std.get("normalized"),
                    raw_example=std.get("raw"),
                )
                if not before:
                    metrics["places_created"] += 1

                rec["counts"]["events"] += 1
                rec["counts"]["family_events"] += 1

                if ev.get("place_id") != place_id:
                    ev["place_id"] = place_id
                    metrics["events_linked"] += 1

    return metrics


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="C.24.5 – Place registry promotion builder")
    p.add_argument("-i", "--input", required=True, help="Input JSON (post place_standardizer or later)")
    p.add_argument("-o", "--output", required=True, help="Output JSON with places registry promoted")
    p.add_argument("--debug", action="store_true", help="Enable debug logging")
    return p


def main(argv: Optional[List[str]] = None) -> None:
    args = build_arg_parser().parse_args(argv)

    if args.debug:
        log.setLevel("DEBUG")

    log.info("Loading input JSON: %s", args.input)
    with open(args.input, "r", encoding="utf-8") as f:
        root = json.load(f)

    metrics = promote_places_registry(root)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(root, f, ensure_ascii=False, indent=2)

    log.info(
        "Place registry promotion complete: places_created=%d places_seen=%d events_seen=%d events_linked=%d "
        "individuals=%d families=%d skipped_non_dict_events=%d",
        metrics["places_created"],
        metrics["places_seen"],
        metrics["events_seen"],
        metrics["events_linked"],
        metrics["individuals_seen"],
        metrics["families_seen"],
        metrics["skipped_non_dict_events"],
    )
    print(f"[INFO] Place registry export written to: {args.output}")


if __name__ == "__main__":
    main()
