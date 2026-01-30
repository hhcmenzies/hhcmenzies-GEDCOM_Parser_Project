"""
place_standardizer.py

C.24.4.10 – Place Standardization

Input  : XREF-enhanced registry JSON (e.g. export_xref.json)
Output : Same registry shape, but events get a `standard_place` block
         when a place string is present.

This version is *conservative*:
- It never changes the overall registry structure.
- It never replaces events with strings.
- It only *adds* `standard_place` dicts when possible.
"""

from __future__ import annotations

import argparse
import json
import logging
from typing import Any, Dict, Tuple, Optional

try:
    from gedcom_parser.logging import get_logger  # project logger
except Exception:  # pragma: no cover - fallback for direct use

    def get_logger(name: str) -> logging.Logger:
        logging.basicConfig(
            level=logging.INFO,
            format="[%(asctime)s] %(levelname)-8s %(name)s: %(message)s",
            datefmt="%m/%d/%y %H:%M:%S",
        )
        return logging.getLogger(name)


log = get_logger("place_standardizer")


# ---------------------------------------------------------------------------
# Simple place normalization / standard_place builder
# ---------------------------------------------------------------------------

def normalize_place_string(raw: str) -> str:
    """
    Minimal normalization of a place string.
    This is deliberately simple and deterministic; you can plug in
    a richer standardization engine later.
    """
    return " ".join(raw.split()).strip()


def build_standard_place(raw: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Given a raw place string, return a standard_place dict or None.

    Standard shape:

        {
            "id": "<normalized-lowercase-id>",
            "raw": "<original string>",
            "normalized": "<cleaned string>"
        }

    This keeps us compatible with later steps that expect a dict with `id`.
    """
    if not raw:
        return None

    raw_str = str(raw)
    normalized = normalize_place_string(raw_str)
    if not normalized:
        return None

    place_id = normalized.lower()

    return {
        "id": place_id,
        "raw": raw_str,
        "normalized": normalized,
    }


# ---------------------------------------------------------------------------
# Core standardization over registry
# ---------------------------------------------------------------------------

def _process_event(evt: Any, counters: Dict[str, int]) -> Any:
    """
    Safely process a single event.

    - If evt is not a dict, leave it exactly as-is (no mutation).
    - If evt is a dict, copy it, add `standard_place` when possible,
      and return the new dict.

    counters is updated in-place for metrics.
    """
    counters["total_events"] += 1

    if not isinstance(evt, dict):
        # This is the critical guard: NEVER treat non-dict events as dicts.
        # We just return it untouched.
        counters["non_dict_events"] += 1
        return evt

    place_raw = evt.get("place")
    std = build_standard_place(place_raw)
    if std is not None:
        new_evt = dict(evt)
        new_evt["standard_place"] = std
        counters["with_places"] += 1
        return new_evt

    return evt


def standardize_registry_places(registry: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, int]]:
    """
    Walk the full registry and add `standard_place` to events
    on individuals and families.

    Returns:
        (new_registry, metrics_dict)
    """
    counters: Dict[str, int] = {
        "individuals": 0,
        "families": 0,
        "total_events": 0,
        "with_places": 0,
        "non_dict_events": 0,
    }

    # Work on a shallow copy of the registry dict so we don't mutate the
    # original reference unexpectedly.
    out: Dict[str, Any] = dict(registry)

    individuals = out.get("individuals", {})
    if isinstance(individuals, dict):
        for indi_id, ind in individuals.items():
            if not isinstance(ind, dict):
                continue
            counters["individuals"] += 1
            events = ind.get("events", [])
            if not isinstance(events, list):
                continue

            new_events = []
            for evt in events:
                new_events.append(_process_event(evt, counters))

            ind["events"] = new_events

    families = out.get("families", {})
    if isinstance(families, dict):
        for fam_id, fam in families.items():
            if not isinstance(fam, dict):
                continue
            counters["families"] += 1
            events = fam.get("events", [])
            if not isinstance(events, list):
                continue

            new_events = []
            for evt in events:
                new_events.append(_process_event(evt, counters))

            fam["events"] = new_events

    return out, counters


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="C.24.4.10 – Place Standardization")
    parser.add_argument(
        "-i",
        "--input",
        required=True,
        help="Input registry JSON (e.g. outputs/export_xref.json)",
    )
    parser.add_argument(
        "-o",
        "--output",
        required=True,
        help="Output registry JSON with standardized places (e.g. outputs/export_places.json)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    if args.debug:
        log.setLevel(logging.DEBUG)

    log.info("Starting place standardization. Input=%s Output=%s", args.input, args.output)

    with open(args.input, "r", encoding="utf-8") as f:
        registry = json.load(f)

    out_registry, counters = standardize_registry_places(registry)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(out_registry, f, indent=2)

    log.info(
        "Place standardization complete: individuals=%d, families=%d, "
        "events=%d, with_places=%d, non_dict_events=%d",
        counters["individuals"],
        counters["families"],
        counters["total_events"],
        counters["with_places"],
        counters["non_dict_events"],
    )
    log.info("Standardized export written to: %s", args.output)

    # Keep the simple stdout confirmation you were seeing:
    print(f"[INFO] Standardized export written to: {args.output}")


if __name__ == "__main__":
    main()
