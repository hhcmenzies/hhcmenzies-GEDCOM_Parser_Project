"""
Entity extractors for INDI, FAM, SOUR, REPO, OBJE.

Includes:
- NAME normalization (C.24.4.2, C.24.4.3)
- Occupation extraction (OCCU + NOTE inference)
- Place blocks (C.24.4.5)
- UUID identity layer (C.24.4.6)
- Event alternates + ambiguity detection (C.24.4.8)
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------
# Imports
# ---------------------------------------------------------

from gedcom_parser.entities.extraction.occupation import (
    extract_occupation_block,
)

from gedcom_parser.entities.extraction.name import (
    parse_name_value,
    merge_name_tags,
)

from gedcom_parser.identity.uuid_factory import (
    uuid_for_record,
    uuid_for_pointer,
    uuid_for_name,
    uuid_for_event,
    uuid_for_occupation,
)

# ==========================================================
# SAFE HELPERS
# ==========================================================

def _safe_place_raw(event_block: Dict[str, Any]) -> str:
    """
    Safely extract raw place text from an event block.

    Handles:
        - event["place"] is missing
        - event["place"] is None
        - event["place"] is a dict { "raw": ... }
    """

    if not isinstance(event_block, dict):
        return ""

    place_block = event_block.get("place")

    if isinstance(place_block, dict):
        return place_block.get("raw") or ""

    # If place exists but is None, maybe raw data still exists
    if place_block is None:
        raw = event_block.get("value")
        return raw or ""

    return ""


# ==========================================================
# PLACE PARSER (lightweight pre-normalizer)
# ==========================================================

def _parse_place(raw: str) -> Dict[str, Optional[str]]:
    """
    Very light-weight place normalization.

    place_standardizer.py (C.24.4.5) will fully standardize
    and assign UUIDs.
    """

    tokens = [t.strip() for t in raw.split(",") if t.strip()]
    parts = {
        "city": None,
        "county": None,
        "state": None,
        "country": None,
    }

    if not tokens:
        return parts

    if len(tokens) == 1:
        parts["city"] = tokens[0]
    elif len(tokens) == 2:
        parts["city"], parts["county"] = tokens
    elif len(tokens) == 3:
        parts["city"], parts["county"], parts["state"] = tokens
    else:
        parts["city"] = tokens[0]
        parts["county"] = tokens[1]
        parts["state"] = tokens[2]
        parts["country"] = tokens[-1]

    return parts


# ==========================================================
# EVENT EXTRACTOR
# ==========================================================

def _extract_event(event_node: Dict[str, Any],
                   record_uuid: Optional[str] = None) -> Dict[str, Any]:
    """
    Extract a single GEDCOM event instance.

    Caller (INDI / FAM extractor) will:
        - attach event-level UUID(s)
        - manage alternates
        - detect ambiguity
    """

    tag = event_node.get("tag")

    event = {
        "tag": tag,
        "date": None,
        "place": None,
        "notes": [],
        "sources": [],
        "raw_children": event_node.get("children", []),
        "uuid": None,
        "ambiguous": False,
    }

    raw_date = None
    raw_place = None

    for sub in event_node.get("children", []):
        st = sub.get("tag")
        val = sub.get("value")

        if st == "DATE":
            raw_date = val
            event["date"] = val

        elif st == "PLAC":
            raw_place = val
            event["place"] = {
                "raw": val,
                "parts": _parse_place(val),
                "coordinates": {"lat": None, "lon": None},
            }

        elif st == "NOTE":
            event["notes"].append(val)

        elif st == "SOUR":
            event["sources"].append(val)

    if record_uuid is not None:
        event["uuid"] = uuid_for_event(
            record_uuid,
            tag or "",
            raw_date or "",
            raw_place or "",
        )

    return event


# ==========================================================
# INDI EXTRACTOR
# ==========================================================

def extract_indi(entity_root: Dict[str, Any]) -> Dict[str, Any]:
    pointer = entity_root.get("pointer")
    indi_uuid = uuid_for_pointer("INDI", pointer)

    out = {
        "uuid": indi_uuid,
        "names": [],
        "name_block": None,
        "sex": None,
        "events": {},
        "attributes": {},
        "occupation": {},
        "relationships": {"FAMC": [], "FAMS": []},
        "sources": [],
        "raw_children": entity_root.get("children", []),
    }

    occu_values: List[str] = []
    note_values: List[str] = []
    name_children: List[Dict[str, Any]] = []

    # ---------------------------------------------------------
    # PASS 1 — scan children
    # ---------------------------------------------------------
    for child in entity_root.get("children", []):
        tag = child["tag"]
        value = child["value"]

        if tag == "NAME":
            out["names"].append(value)
            name_children = child.get("children", [])

        elif tag == "SEX":
            out["sex"] = value.strip()

        elif tag in ("FAMC", "FAMS"):
            out["relationships"][tag].append(value)

        elif tag in ("BIRT", "DEAT", "CHR", "BAPM", "BURI", "MARR"):
            ev = _extract_event(child, record_uuid=indi_uuid)
            existing = out["events"].get(tag)

            if existing is None:
                out["events"][tag] = ev
            else:
                alts = existing.setdefault("alternates", [])
                alts.append(ev)

                # ambiguity detection
                if (ev.get("date") != existing.get("date")) or (
                    _safe_place_raw(ev) != _safe_place_raw(existing)
                ):
                    existing["ambiguous"] = True

        elif tag == "OCCU":
            occu_values.append(value)

        elif tag == "NOTE":
            note_values.append(value)

        elif tag in ("EDUC", "TITL", "NATI", "RELI"):
            out["attributes"].setdefault(tag, []).append(value)

        elif tag == "SOUR":
            out["sources"].append(value)

    # ---------------------------------------------------------
    # PASS 2 — Name normalization + name UUID
    # ---------------------------------------------------------
    if out["names"]:
        primary = out["names"][0]
        base_block = parse_name_value(primary)
        enriched = merge_name_tags(base_block, name_children)

        enriched["uuid"] = uuid_for_name(
            pointer,
            enriched.get("full_name_normalized") or primary
        )

        out["name_block"] = enriched

    # ---------------------------------------------------------
    # PASS 3 — Occupation + UUID
    # ---------------------------------------------------------
    occ_block = extract_occupation_block(occu_values, note_values)
    if occ_block:
        occ_block["uuid"] = uuid_for_occupation(
            indi_uuid,
            occ_block.get("primary") or "",
        )
    out["occupation"] = occ_block

    return out


# ==========================================================
# FAMILY EXTRACTOR
# ==========================================================

def extract_family(entity_root: Dict[str, Any]) -> Dict[str, Any]:
    pointer = entity_root.get("pointer")
    fam_uuid = uuid_for_pointer("FAM", pointer)

    out = {
        "uuid": fam_uuid,
        "members": {"husband": None, "wife": None, "children": []},
        "events": {},
        "raw_children": entity_root.get("children", []),
    }

    for child in entity_root.get("children", []):
        tag = child["tag"]
        val = child["value"]

        if tag == "HUSB":
            out["members"]["husband"] = val
        elif tag == "WIFE":
            out["members"]["wife"] = val
        elif tag == "CHIL":
            out["members"]["children"].append(val)

        elif tag == "MARR":
            ev = _extract_event(child, record_uuid=fam_uuid)
            primary = out["events"].get(tag)

            if primary is None:
                out["events"][tag] = ev
            else:
                alts = primary.setdefault("alternates", [])
                alts.append(ev)

                if (ev.get("date") != primary.get("date")) or (
                    _safe_place_raw(ev) != _safe_place_raw(primary)
                ):
                    primary["ambiguous"] = True

    return out


# ==========================================================
# SOUR / REPO / OBJE
# ==========================================================

def extract_source(entity_root: Dict[str, Any]) -> Dict[str, Any]:
    pointer = entity_root.get("pointer")
    src_uuid = uuid_for_pointer("SOUR", pointer)

    meta = {
        "uuid": src_uuid,
        "title": None,
        "author": None,
        "publication": None,
        "repo": None,
        "notes": [],
        "raw_children": entity_root.get("children", []),
    }

    for child in entity_root.get("children", []):
        tag = child["tag"]
        val = child["value"]

        if tag == "TITL":
            meta["title"] = val
        elif tag == "AUTH":
            meta["author"] = val
        elif tag == "PUBL":
            meta["publication"] = val
        elif tag == "REPO":
            meta["repo"] = val
        elif tag == "NOTE":
            meta["notes"].append(val)

    return meta


def extract_repository(entity_root: Dict[str, Any]) -> Dict[str, Any]:
    pointer = entity_root.get("pointer")
    repo_uuid = uuid_for_pointer("REPO", pointer)

    meta = {
        "uuid": repo_uuid,
        "name": None,
        "address": None,
        "notes": [],
        "raw_children": entity_root.get("children", []),
    }

    for child in entity_root.get("children", []):
        tag = child["tag"]
        val = child["value"]

        if tag == "NAME":
            meta["name"] = val
        elif tag == "ADDR":
            meta["address"] = val
        elif tag == "NOTE":
            meta["notes"].append(val)

    return meta


def extract_media_object(entity_root: Dict[str, Any]) -> Dict[str, Any]:
    pointer = entity_root.get("pointer")
    obje_uuid = uuid_for_pointer("OBJE", pointer)

    meta = {
        "uuid": obje_uuid,
        "file": None,
        "form": None,
        "title": None,
        "notes": [],
        "raw_children": entity_root.get("children", []),
    }

    for child in entity_root.get("children", []):
        tag = child["tag"]
        val = child["value"]

        if tag == "FILE":
            meta["file"] = val
        elif tag == "FORM":
            meta["form"] = val
        elif tag == "TITL":
            meta["title"] = val
        elif tag == "NOTE":
            meta["notes"].append(val)

    return meta
