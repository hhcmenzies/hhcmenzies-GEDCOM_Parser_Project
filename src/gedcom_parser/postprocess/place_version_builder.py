# src/gedcom_parser/postprocess/place_version_builder.py
"""
place_version_builder.py

C.24.7 – Temporal & Jurisdiction Layers (Place Versioning + event.place_refs)

Input : C.24.6 canonical export JSON (export_c24_6.json)
Output: Same registry shape, plus:
    - root["jurisdiction_systems"] registry
    - root["place_versions"] registry
    - optional per-event event["place_refs"] list (config/CLI-controlled)

Design goals
-----------
- Works directly on modern export JSON dicts (no dataclasses, no pydantic).
- Never deletes or restructures existing data.
- Idempotent: safe to run multiple times.
- Deterministic IDs.
- All defaulted / inferred fields can be tagged with `generated` metadata for future enrichment.

Key semantics
-------------
- event.place_id continues to mean "the canonical place reference (C.24.5/6)".
- event.place_refs (C.24.7) are *interpretations* of that same place_id across:
    - jurisdiction system
    - temporal bucket (YEAR by default)
  NOT multiple physical PLAC values per GEDCOM event.

Example event.place_refs entry:
{
  "place_id": "<existing event.place_id>",
  "place_version_id": "pv_<sha1>",
  "jurisdiction_system_id": "js:civil-us",
  "temporal": {"bucket": "year", "year": 1912},   # or {"bucket":"year","open_ended":true}
  "generated": {
      "by": "place_version_builder",
      "rule": "year_from_event_date" | "open_ended_no_date",
      "inferred": true|false,
      "enrichment_candidate": true|false,
      "confidence": 0.0..1.0
  }
}

Place version record (minimal, forward-compatible):
{
  "id": "pv_<sha1>",
  "place_id": "<place_id>",
  "jurisdiction_system_id": "js:civil-us",
  "temporal": {"bucket":"year","year":1912} OR {"bucket":"year","open_ended":true},
  "generated": {...},
  "meta": {
      "events": <int>,
      "individual_events": <int>,
      "family_events": <int>
  }
}

Configuration
-------------
This module supports:
- CLI flags
- Optional YAML config file (config/gedcom_parser.yml) if PyYAML is installed
  (if not installed, YAML is ignored safely).

Recommended config keys (if you wire it later):
place_processing:
  enable_place_versions: true
  enable_event_place_refs: true
  allow_multiple_place_refs_per_event: false
  default_jurisdiction_system: js:civil-us
  jurisdiction_systems_enabled:
    - js:civil-us
  temporal:
    bucket: year
    open_ended_fallback: true
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from gedcom_parser.logger import get_logger

log = get_logger("place_version_builder")

_YEAR_RE = re.compile(r"(?<!\d)(\d{4})(?!\d)")


# -----------------------------------------------------------------------------
# Config loading (optional)
# -----------------------------------------------------------------------------

def _load_yaml_if_available(path: str) -> Dict[str, Any]:
    """
    Best-effort YAML loader. If PyYAML isn't installed or file missing, return {}.
    """
    if not path or not os.path.exists(path):
        return {}
    try:
        import yaml  # type: ignore
    except Exception:
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _get_cfg_value(cfg: Dict[str, Any], keys: List[str], default: Any) -> Any:
    """
    Traverse nested dict safely.
    keys like ["place_processing","temporal","bucket"]
    """
    cur: Any = cfg
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


# -----------------------------------------------------------------------------
# Utilities
# -----------------------------------------------------------------------------

def _sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def _as_bool(v: Any) -> bool:
    return bool(v is True or (isinstance(v, str) and v.strip().lower() in ("1", "true", "yes", "y", "on")))


def _is_event_dict(ev: Any) -> bool:
    return isinstance(ev, dict)


def _iter_records(root: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
    """
    Return list of (group, record_dict) where group in {"individuals","families"}.
    """
    out: List[Tuple[str, Dict[str, Any]]] = []
    for group in ("individuals", "families"):
        g = root.get(group, {})
        if not isinstance(g, dict):
            continue
        for _ptr, rec in g.items():
            if isinstance(rec, dict):
                out.append((group, rec))
    return out


def _iter_events(rec: Dict[str, Any]) -> List[Any]:
    evs = rec.get("events", [])
    return evs if isinstance(evs, list) else []


def _extract_year_from_date_block(date_block: Any) -> Optional[int]:
    """
    Handles the modern event date shape you have in exports:
      - None
      - string
      - dict with keys like:
          normalized: "1979-10-19"
          raw: "19 Oct 1979"
          kind/modifier...
          start/end...
    Strategy: find first 4-digit year in normalized/raw/string.
    """
    if not date_block:
        return None

    if isinstance(date_block, int):
        # unlikely, but accept
        return int(date_block)

    if isinstance(date_block, str):
        m = _YEAR_RE.search(date_block)
        return int(m.group(1)) if m else None

    if isinstance(date_block, dict):
        for k in ("date", "normalized", "raw", "start", "end"):
            val = date_block.get(k)
            if isinstance(val, str):
                m = _YEAR_RE.search(val)
                if m:
                    return int(m.group(1))
        # Sometimes start/end may be dicts; try recursively
        for k in ("start", "end"):
            val = date_block.get(k)
            if isinstance(val, dict):
                y = _extract_year_from_date_block(val)
                if y is not None:
                    return y

    return None


def _event_year_bucket(ev: Dict[str, Any]) -> Tuple[Optional[int], str, bool]:
    """
    Returns: (year_or_none, rule, inferred)
    """
    y = _extract_year_from_date_block(ev.get("date"))
    if y is not None:
        return (y, "year_from_event_date", False)

    # Try other possible date-like hints (very conservative)
    if isinstance(ev.get("value"), str):
        m = _YEAR_RE.search(ev["value"])
        if m:
            return (int(m.group(1)), "year_from_event_value_fallback", True)

    return (None, "open_ended_no_date", True)


def _ensure_dict(root: Dict[str, Any], key: str) -> Dict[str, Any]:
    val = root.get(key)
    if isinstance(val, dict):
        return val
    d: Dict[str, Any] = {}
    root[key] = d
    return d


# -----------------------------------------------------------------------------
# Jurisdiction systems
# -----------------------------------------------------------------------------

def _ensure_jurisdiction_systems(
    root: Dict[str, Any],
    default_js_id: str,
    enabled_js_ids: List[str],
) -> Dict[str, Any]:
    """
    Ensure root["jurisdiction_systems"] exists and has at least the default system.
    """
    systems = _ensure_dict(root, "jurisdiction_systems")

    def _ensure_one(js_id: str) -> None:
        if js_id in systems and isinstance(systems[js_id], dict):
            systems[js_id].setdefault("id", js_id)
            return

        # Minimal, forward-compatible record
        # You can expand later with: {"kind":"civil","country":"US",...}
        systems[js_id] = {
            "id": js_id,
            "name": js_id,
            "generated": {
                "by": "place_version_builder",
                "rule": "ensure_default_jurisdiction_system",
                "inferred": True,
                "enrichment_candidate": False,
                "confidence": 0.9,
            },
        }

    # Ensure default exists
    _ensure_one(default_js_id)

    # Ensure enabled exist
    for js_id in enabled_js_ids:
        _ensure_one(js_id)

    return systems


# -----------------------------------------------------------------------------
# Place versions
# -----------------------------------------------------------------------------

def _place_version_id(place_id: str, js_id: str, year: Optional[int]) -> str:
    """
    Deterministic ID. Stable across runs, independent of insertion order.
    """
    key = f"{place_id}|{js_id}|{year if year is not None else '..'}"
    return "pv_" + _sha1(key)[:20]


def _temporal_block(bucket: str, year: Optional[int]) -> Dict[str, Any]:
    if bucket != "year":
        # only year is supported for now; keep forward compatible
        return {"bucket": bucket, "open_ended": True}
    if year is None:
        return {"bucket": "year", "open_ended": True}
    return {"bucket": "year", "year": int(year)}


def _ensure_place_version(
    place_versions: Dict[str, Any],
    place_id: str,
    js_id: str,
    bucket: str,
    year: Optional[int],
    generated: Dict[str, Any],
) -> Tuple[str, Dict[str, Any], bool]:
    """
    Ensure a place_versions[pv_id] record exists. Return (pv_id, record, created_bool).
    """
    pv_id = _place_version_id(place_id, js_id, year)
    rec = place_versions.get(pv_id)

    if isinstance(rec, dict):
        # Backfill minimal shape without overwriting richer existing fields.
        rec.setdefault("id", pv_id)
        rec.setdefault("place_id", place_id)
        rec.setdefault("jurisdiction_system_id", js_id)
        rec.setdefault("temporal", _temporal_block(bucket, year))
        rec.setdefault("meta", {})
        if isinstance(rec.get("meta"), dict):
            rec["meta"].setdefault("events", 0)
            rec["meta"].setdefault("individual_events", 0)
            rec["meta"].setdefault("family_events", 0)
        rec.setdefault("generated", generated)
        return pv_id, rec, False

    rec = {
        "id": pv_id,
        "place_id": place_id,
        "jurisdiction_system_id": js_id,
        "temporal": _temporal_block(bucket, year),
        "generated": generated,
        "meta": {"events": 0, "individual_events": 0, "family_events": 0},
    }
    place_versions[pv_id] = rec
    return pv_id, rec, True


def _ensure_event_place_refs_container(ev: Dict[str, Any]) -> List[Any]:
    """
    Ensure ev["place_refs"] exists as a list. Return it.
    """
    pr = ev.get("place_refs")
    if isinstance(pr, list):
        return pr
    pr = []
    ev["place_refs"] = pr
    return pr


def _event_already_has_ref(ev: Dict[str, Any], pv_id: str, js_id: str) -> bool:
    pr = ev.get("place_refs")
    if not isinstance(pr, list):
        return False
    for item in pr:
        if isinstance(item, dict) and item.get("place_version_id") == pv_id and item.get("jurisdiction_system_id") == js_id:
            return True
    return False


# -----------------------------------------------------------------------------
# Core builder
# -----------------------------------------------------------------------------

def build_place_versions_and_refs(
    root: Dict[str, Any],
    *,
    enable_place_versions: bool = True,
    enable_event_place_refs: bool = True,
    allow_multiple_place_refs_per_event: bool = False,
    default_jurisdiction_system_id: str = "js:civil-us",
    jurisdiction_systems_enabled: Optional[List[str]] = None,
    temporal_bucket: str = "year",
    open_ended_fallback: bool = True,
) -> Dict[str, int]:
    """
    Mutates root in-place (additive, idempotent). Returns metrics dict.
    """
    metrics: Dict[str, int] = {
        "events_seen": 0,
        "events_with_place_id": 0,
        "events_place_refs_added": 0,
        "events_place_refs_skipped_existing": 0,
        "events_place_refs_skipped_disabled": 0,
        "events_place_refs_skipped_no_place_id": 0,
        "events_place_refs_skipped_multiple_not_allowed": 0,
        "places_versions_created": 0,
        "place_versions_seen": 0,
        "place_versions_updated_meta": 0,
        "skipped_non_dict_events": 0,
    }

    if not isinstance(root, dict):
        return metrics

    enabled_js = jurisdiction_systems_enabled or [default_jurisdiction_system_id]
    _ensure_jurisdiction_systems(root, default_jurisdiction_system_id, enabled_js)

    place_versions = _ensure_dict(root, "place_versions")

    # Walk all INDI/FAM events
    for group, rec in _iter_records(root):
        for ev_any in _iter_events(rec):
            metrics["events_seen"] += 1
            if not _is_event_dict(ev_any):
                metrics["skipped_non_dict_events"] += 1
                continue
            ev: Dict[str, Any] = ev_any

            place_id = ev.get("place_id")
            if not place_id or not isinstance(place_id, str):
                metrics["events_place_refs_skipped_no_place_id"] += 1
                continue

            metrics["events_with_place_id"] += 1

            # Determine year bucket
            year, rule, inferred = _event_year_bucket(ev)
            if year is None and not open_ended_fallback:
                # If open-ended disabled, we refuse to create versions/refs without a year
                # (but still keep existing place_id untouched)
                continue

            # For C.24.7 we default to emitting just one ref unless user enables more.
            js_targets = [default_jurisdiction_system_id]

            # Build / update place versions
            if enable_place_versions:
                for js_id in js_targets:
                    generated = {
                        "by": "place_version_builder",
                        "rule": rule,
                        "inferred": bool(inferred),
                        "enrichment_candidate": bool(inferred),
                        "confidence": 0.6 if inferred else 0.95,
                    }
                    pv_id, pv_rec, created = _ensure_place_version(
                        place_versions,
                        place_id=place_id,
                        js_id=js_id,
                        bucket=temporal_bucket,
                        year=year,
                        generated=generated,
                    )
                    metrics["place_versions_seen"] += 1
                    if created:
                        metrics["places_versions_created"] += 1

                    # Update meta counters
                    meta = pv_rec.get("meta")
                    if isinstance(meta, dict):
                        meta["events"] = int(meta.get("events", 0)) + 1
                        if group == "individuals":
                            meta["individual_events"] = int(meta.get("individual_events", 0)) + 1
                        elif group == "families":
                            meta["family_events"] = int(meta.get("family_events", 0)) + 1
                        metrics["place_versions_updated_meta"] += 1

            # Add event.place_refs (optional)
            if not enable_event_place_refs:
                metrics["events_place_refs_skipped_disabled"] += 1
                continue

            # If multiple refs not allowed, and place_refs already exists with content, skip.
            existing_pr = ev.get("place_refs")
            if (not allow_multiple_place_refs_per_event) and isinstance(existing_pr, list) and len(existing_pr) > 0:
                metrics["events_place_refs_skipped_multiple_not_allowed"] += 1
                continue

            # Ensure ref exists (idempotent)
            for js_id in js_targets:
                pv_id = _place_version_id(place_id, js_id, year)
                if _event_already_has_ref(ev, pv_id, js_id):
                    metrics["events_place_refs_skipped_existing"] += 1
                    continue

                pr_list = _ensure_event_place_refs_container(ev)
                pr_list.append(
                    {
                        "place_id": place_id,
                        "place_version_id": pv_id,
                        "jurisdiction_system_id": js_id,
                        "temporal": _temporal_block(temporal_bucket, year),
                        "generated": {
                            "by": "place_version_builder",
                            "rule": rule,
                            "inferred": bool(inferred),
                            "enrichment_candidate": bool(inferred),
                            "confidence": 0.6 if inferred else 0.95,
                        },
                    }
                )
                metrics["events_place_refs_added"] += 1

    return metrics


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="C.24.7 – Place versioning + event.place_refs builder")
    p.add_argument("-i", "--input", required=True, help="Input JSON (C.24.6 export, e.g. outputs/export_c24_6.json)")
    p.add_argument("-o", "--output", required=True, help="Output JSON (C.24.7 export, e.g. outputs/export_c24_7.json)")

    # Config file (optional)
    p.add_argument("--config", default="config/gedcom_parser.yml", help="Optional YAML config path")

    # Feature toggles
    p.add_argument("--enable-place-versions", action="store_true", default=None, help="Enable root.place_versions (default: from config or True)")
    p.add_argument("--disable-place-versions", action="store_true", help="Disable root.place_versions")

    p.add_argument("--enable-event-place-refs", action="store_true", default=None, help="Enable event.place_refs (default: from config or True)")
    p.add_argument("--disable-event-place-refs", action="store_true", help="Disable event.place_refs")

    p.add_argument("--allow-multiple-place-refs", action="store_true", default=None, help="Allow multiple place_refs per event (default: from config or False)")

    # Jurisdiction + temporal
    p.add_argument("--default-jurisdiction", default=None, help="Default jurisdiction_system_id (e.g. js:civil-us)")
    p.add_argument("--jurisdiction-enabled", action="append", default=None, help="Enable additional jurisdiction_system_id (repeatable)")
    p.add_argument("--bucket", default=None, choices=["year"], help="Temporal bucket (C.24.7: year)")
    p.add_argument("--no-open-ended-fallback", action="store_true", help="If set, do not create open-ended temporal for missing dates")

    p.add_argument("--debug", action="store_true", help="Enable debug logging")
    return p


def main(argv: Optional[List[str]] = None) -> None:
    args = build_arg_parser().parse_args(argv)

    if args.debug:
        log.setLevel("DEBUG")

    cfg = _load_yaml_if_available(args.config)
    pp = _get_cfg_value(cfg, ["place_processing"], {}) if isinstance(cfg, dict) else {}

    # Resolve effective settings (CLI overrides config; config overrides defaults)
    enable_place_versions = True
    enable_event_place_refs = True
    allow_multiple_place_refs = False

    # From config if present
    if isinstance(pp, dict):
        enable_place_versions = _as_bool(pp.get("enable_place_versions", enable_place_versions))
        enable_event_place_refs = _as_bool(pp.get("enable_event_place_refs", enable_event_place_refs))
        allow_multiple_place_refs = _as_bool(pp.get("allow_multiple_place_refs_per_event", allow_multiple_place_refs))

    # CLI hard overrides
    if args.disable_place_versions:
        enable_place_versions = False
    elif args.enable_place_versions is True:
        enable_place_versions = True

    if args.disable_event_place_refs:
        enable_event_place_refs = False
    elif args.enable_event_place_refs is True:
        enable_event_place_refs = True

    if args.allow_multiple_place_refs is True:
        allow_multiple_place_refs = True

    default_js = (
        args.default_jurisdiction
        or (pp.get("default_jurisdiction_system") if isinstance(pp, dict) else None)
        or "js:civil-us"
    )

    enabled_js = args.jurisdiction_enabled
    if enabled_js is None:
        enabled_js = (pp.get("jurisdiction_systems_enabled") if isinstance(pp, dict) else None)
    if not isinstance(enabled_js, list) or not enabled_js:
        enabled_js = [default_js]
    if default_js not in enabled_js:
        enabled_js = [default_js] + enabled_js

    bucket = args.bucket or _get_cfg_value(cfg, ["place_processing", "temporal", "bucket"], "year")
    if bucket != "year":
        bucket = "year"

    open_ended_fallback = not bool(args.no_open_ended_fallback)
    if isinstance(pp, dict):
        open_ended_fallback = _as_bool(_get_cfg_value(cfg, ["place_processing", "temporal", "open_ended_fallback"], open_ended_fallback))

    log.info("Loading input JSON: %s", args.input)
    with open(args.input, "r", encoding="utf-8") as f:
        root = json.load(f)

    metrics = build_place_versions_and_refs(
        root,
        enable_place_versions=enable_place_versions,
        enable_event_place_refs=enable_event_place_refs,
        allow_multiple_place_refs_per_event=allow_multiple_place_refs,
        default_jurisdiction_system_id=default_js,
        jurisdiction_systems_enabled=enabled_js,
        temporal_bucket=bucket,
        open_ended_fallback=open_ended_fallback,
    )

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(root, f, ensure_ascii=False, indent=2)

    log.info(
        "C.24.7 place versioning complete: events_seen=%d events_with_place_id=%d "
        "place_versions_created=%d place_versions_seen=%d refs_added=%d skipped_existing=%d "
        "skipped_disabled=%d skipped_no_place_id=%d skipped_multiple_not_allowed=%d",
        metrics["events_seen"],
        metrics["events_with_place_id"],
        metrics["places_versions_created"],
        metrics["place_versions_seen"],
        metrics["events_place_refs_added"],
        metrics["events_place_refs_skipped_existing"],
        metrics["events_place_refs_skipped_disabled"],
        metrics["events_place_refs_skipped_no_place_id"],
        metrics["events_place_refs_skipped_multiple_not_allowed"],
    )
    print(f"[INFO] C.24.7 export written to: {args.output}")

# Backward-compatible public API
build_place_versions = build_place_versions_and_refs

if __name__ == "__main__":
    main()
