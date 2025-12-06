"""
C.24.4.5 - Place Standardization Post-Processor (Option B)

Responsibilities:
- Walk all individuals and families.
- Standardize every event's place field (including alternates).
- Preserve original raw place text.
- Normalize simple country/state variants.
- Build a stable UUID5 for each distinct place.
- Insert a structured "standard_place" block on each event.
"""

import argparse
import json
import uuid
from typing import Any, Dict, Iterable, Tuple

from gedcom_parser.logging import get_logger

log = get_logger("place_standardizer")

# Deterministic namespace UUID for place IDs
PLACE_NAMESPACE_UUID = uuid.UUID("c7a6f962-4b2e-4d30-9b21-9a9daf0d2b11")

COUNTRY_MAP: Dict[str, str] = {
    "usa": "United States",
    "u.s.a": "United States",
    "u.s.": "United States",
    "us": "United States",
    "united states of america": "United States",
    "uk": "United Kingdom",
    "eng": "England",
}

STATE_MAP: Dict[str, str] = {
    "ca": "California",
    "calif": "California",
    "ny": "New York",
    "tx": "Texas",
    "fl": "Florida",
    "oh": "Ohio",
}


def _normalize_component(text: str) -> str:
    """Normalize a single place component using COUNTRY_MAP/STATE_MAP."""
    if not text:
        return ""
    t = text.strip()
    low = t.lower()
    if low in COUNTRY_MAP:
        return COUNTRY_MAP[low]
    if low in STATE_MAP:
        return STATE_MAP[low]
    return t


def _standardize_place_block(place_block: Dict[str, Any]) -> Dict[str, Any]:
    """
    Given an existing place block of the form:
        {
            "raw": "...",
            "parts": {
                "city": ...,
                "county": ...,
                "state": ...,
                "country": ...
            },
            "coordinates": {...}
        }

    Build a canonical standard_place structure and return it.
    """
    raw = place_block.get("raw") or ""
    parts = place_block.get("parts") or {}

    city = _normalize_component(parts.get("city") or "")
    county = _normalize_component(parts.get("county") or "")
    state = _normalize_component(parts.get("state") or "")
    country = _normalize_component(parts.get("country") or "")

    norm_parts = {
        "city": city or None,
        "county": county or None,
        "state": state or None,
        "country": country or None,
    }

    # Hierarchy string from available fields
    hierarchy_components = [c for c in [city, county, state, country] if c]
    hierarchy = ", ".join(hierarchy_components)

    # Deterministic UUID using raw string; if raw is missing, fall back to hierarchy
    key = raw.strip() or hierarchy
    place_id = str(uuid.uuid5(PLACE_NAMESPACE_UUID, key)) if key else None

    standard_place = {
        "id": place_id,
        "hierarchy": hierarchy,
        "parts": norm_parts,
        "raw": raw,
    }
    return standard_place


def _process_single_event(event: Dict[str, Any]) -> Tuple[int, int]:
    """
    Process a single event dict.

    Returns (events_seen, events_with_place) for counters.
    """
    if not isinstance(event, dict):
        return 0, 0

    events_seen = 1
    events_with_place = 0

    place = event.get("place")
    if isinstance(place, dict):
        event["standard_place"] = _standardize_place_block(place)
        events_with_place += 1

    # Alternates (if present)
    alternates = event.get("alternates") or []
    if isinstance(alternates, list):
        for alt in alternates:
            if not isinstance(alt, dict):
                continue
            alt_place = alt.get("place")
            if isinstance(alt_place, dict):
                alt["standard_place"] = _standardize_place_block(alt_place)
                events_with_place += 1
                events_seen += 1

    return events_seen, events_with_place


def _iter_events_from_record(record: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    """
    Yield all event dicts from an individual or family record.

    For your current registry structure, events live at:
        record["events"] -> {TAG: event or [event, ...]}
    """
    if not isinstance(record, dict):
        return []

    events_by_tag = record.get("events") or {}
    if not isinstance(events_by_tag, dict):
        return []

    for tag, ev_block in events_by_tag.items():
        # ev_block can be a dict (single event) or a list of events
        if isinstance(ev_block, dict):
            yield ev_block
        elif isinstance(ev_block, list):
            for ev in ev_block:
                if isinstance(ev, dict):
                    yield ev


def standardize_places(registry: Dict[str, Any]) -> Dict[str, Any]:
    """
    Walk the individuals and families collections and standardize places.
    """
    individuals = registry.get("individuals") or {}
    families = registry.get("families") or {}

    events_seen = 0
    events_with_places = 0

    # Individuals
    for ptr, person in individuals.items():
        for ev in _iter_events_from_record(person):
            seen, with_place = _process_single_event(ev)
            events_seen += seen
            events_with_places += with_place

    # Families
    for fptr, fam in families.items():
        for ev in _iter_events_from_record(fam):
            seen, with_place = _process_single_event(ev)
            events_seen += seen
            events_with_places += with_place

    log.info(
        "Place standardization complete: individuals=%d, families=%d, events=%d, with_places=%d",
        len(individuals),
        len(families),
        events_seen,
        events_with_places,
    )

    return registry


def main() -> None:
    parser = argparse.ArgumentParser(description="GEDCOM Place Standardizer (Option B)")
    parser.add_argument(
        "-i", "--input", required=True, help="Input JSON file (e.g. outputs/export_xref.json)"
    )
    parser.add_argument(
        "-o",
        "--output",
        required=True,
        help="Output JSON file (e.g. outputs/export_standardized.json)",
    )
    parser.add_argument(
        "--debug", action="store_true", help="Enable debug logging for place_standardizer"
    )
    args = parser.parse_args()

    if args.debug:
        log.setLevel("DEBUG")

    log.info("Starting place standardization. Input=%s Output=%s", args.input, args.output)

    with open(args.input, "r", encoding="utf-8") as f:
        registry = json.load(f)

    updated = standardize_places(registry)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(updated, f, indent=2, ensure_ascii=False)

    log.info("Standardized export written to: %s", args.output)
    print(f"[INFO] Standardized export written to: {args.output}")


if __name__ == "__main__":
    main()
