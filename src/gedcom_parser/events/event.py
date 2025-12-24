# src/gedcom_parser/events/event.py

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as Date
from typing import Any, Dict, List, Optional
import re

from gedcom_parser.dates.normalizer import parse_date


# ---------------------------------------------------------------------------
# Event Tag Definitions (GEDCOM 5.5.1 / 5.5.5)
# ---------------------------------------------------------------------------

INDIVIDUAL_EVENT_TAGS: set[str] = {
    "BIRT", "CHR", "CHRA", "BAPM", "BARM", "BASM", "BLES",
    "ADOP", "CONF", "FCOM", "GRAD", "ORDN", "EMIG", "IMMI",
    "NATU", "CENS", "PROB", "WILL", "RETI", "DEAT", "BURI",
    "CREM", "EVEN",  # EVEN = generic event
}

FAMILY_EVENT_TAGS: set[str] = {
    "MARR", "MARB", "MARC", "MARL", "MARS",
    "ENGA", "ANUL", "DIV", "DIVF",
}

# Core role-like tags
ROLE_TAGS_CORE: set[str] = {
    "HUSB", "WIFE", "CHIL", "ASSO", "ROLE",
}

# Tags that are explicitly *not* roles
NON_ROLE_TAGS: set[str] = {
    "DATE", "PLAC", "NOTE", "SOUR", "CONC", "CONT",
    "MAP", "LATI", "LONG", "OBJE", "TYPE", "CAUS", "QUAY",
}

# Event type normalization map
EVENT_TYPE_MAP: Dict[str, str] = {
    "BIRT": "Birth",
    "CHR": "Christening",
    "CHRA": "Adult Christening",
    "BAPM": "Baptism",
    "BARM": "Bar Mitzvah",
    "BASM": "Bas Mitzvah",
    "ADOP": "Adoption",
    "MARR": "Marriage",
    "DIV": "Divorce",
    "ENGA": "Engagement",
    "DEAT": "Death",
    "BURI": "Burial",
    "CREM": "Cremation",
    "EMIG": "Emigration",
    "IMMI": "Immigration",
    "NATU": "Naturalization",
    "CENS": "Census",
    "GRAD": "Graduation",
    "WILL": "Will",
    "OCCU": "Occupation",
    "RETI": "Retirement",
    "EVEN": "Event",
}


# ---------------------------------------------------------------------------
# Event + Roles
# ---------------------------------------------------------------------------

@dataclass
class EventRole:
    """Represents an individual's role in a shared event."""
    tag: str
    value: Optional[str] = None
    normalized: Optional[str] = None


@dataclass
class Event:
    """
    A structured genealogical event extracted from a GEDCOM record.
    """
    uuid: str
    tag: str

    # Core semantics
    date: Optional[Dict[str, Any]] = None
    place: Optional[str] = None
    value: Optional[str] = None
    notes: List[str] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    roles: List[EventRole] = field(default_factory=list)
    pointer: Optional[str] = None
    lineno: Optional[int] = None

    # Enrichment (Step 3.3)
    type: Optional[str] = None
    subtype: Optional[str] = None
    description: Optional[str] = None
    certainty: Optional[int] = None
    cause: Optional[str] = None
    age: Optional[Dict[str, Any]] = None
    location: Optional[Dict[str, float]] = None


# ---------------------------------------------------------------------------
# Tag Helpers
# ---------------------------------------------------------------------------

def is_event_tag(tag: str) -> bool:
    """Return True if the tag is any known individual or family event tag."""
    if not tag:
        return False
    t = tag.upper()
    return t in INDIVIDUAL_EVENT_TAGS or t in FAMILY_EVENT_TAGS


def is_family_event_tag(tag: str) -> bool:
    return tag.upper() in FAMILY_EVENT_TAGS if tag else False


def is_individual_event_tag(tag: str) -> bool:
    """Legacy-compatible helper."""
    if not tag:
        return False
    return tag.upper() in INDIVIDUAL_EVENT_TAGS


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _trim(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    s = s.strip()
    return s or None


def _normalize_place_str(place: str) -> str:
    """
    Basic place normalization:
      - strip leading/trailing whitespace
      - collapse internal whitespace
      - normalize spaces around commas
    """
    s = place.strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s*,\s*", ", ", s)
    return s


def _extract_child_value(node: Dict[str, Any], tag: str) -> Optional[str]:
    """Find first child of `node` with the given tag and return its trimmed value."""
    for child in node.get("children", []):
        if child.get("tag", "").upper() == tag:
            return _trim(child.get("value"))
    return None


def _extract_child_nodes(node: Dict[str, Any], tag: str) -> List[Dict[str, Any]]:
    """Return all children matching a tag."""
    return [
        c
        for c in node.get("children", [])
        if c.get("tag", "").upper() == tag
    ]


# ---------------------------------------------------------------------------
# Notes, Sources, Place, Date
# ---------------------------------------------------------------------------

def _extract_notes(node: Dict[str, Any]) -> List[str]:
    """
    Extract NOTE text from direct NOTE children of the event node.

    Value reconstruction (CONC/CONT) has already been applied upstream,
    so each NOTE.value is a fully reconstructed multi-line string.
    """
    notes: List[str] = []
    for child in _extract_child_nodes(node, "NOTE"):
        val = _trim(child.get("value"))
        if val:
            notes.append(val)
    return notes


def _extract_sources(node: Dict[str, Any]) -> List[str]:
    """
    Extract all SOUR child pointers from the event node.

    We do not yet parse source structure (TITL, AUTH, etc.) here.
    """
    sources: List[str] = []
    for child in _extract_child_nodes(node, "SOUR"):
        ptr = _trim(child.get("pointer") or child.get("value"))
        if ptr and ptr.startswith("@") and ptr.endswith("@"):
            sources.append(ptr)
    return sources


def _extract_place(node: Dict[str, Any]) -> Optional[str]:
    """Extract and normalize PLAC value if present."""
    raw = _extract_child_value(node, "PLAC")
    if not raw:
        return None
    return _normalize_place_str(raw)


def _extract_date(node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract DATE child and pass through date normalizer."""
    dval = _extract_child_value(node, "DATE")
    if not dval:
        return None
    return parse_date(dval)


# ---------------------------------------------------------------------------
# Role Extraction (Hybrid: metadata-informed + fallback)
# ---------------------------------------------------------------------------

def _looks_like_pointer(value: Optional[str]) -> bool:
    if not value:
        return False
    v = value.strip()
    return v.startswith("@") and v.endswith("@") and len(v) >= 3


def _is_role_candidate(tag: str, node: Dict[str, Any]) -> bool:
    """
    Decide if a given tag/node pair represents a participant role.

    Hybrid logic:
      - tag in ROLE_TAGS_CORE → always a role
      - tag starts with '_' and value/pointer looks like @XREF@ → role
      - tag in NON_ROLE_TAGS → not a role
    """
    if not tag:
        return False

    t = tag.upper()

    if t in ROLE_TAGS_CORE:
        return True

    if t in NON_ROLE_TAGS:
        return False

    # Custom role tags: user extensions, e.g. _WITN
    if t.startswith("_"):
        ptr = node.get("pointer") or node.get("value")
        return _looks_like_pointer(ptr)

    return False


_ROLE_LABELS: Dict[str, str] = {
    "HUSB": "Husband",
    "WIFE": "Wife",
    "CHIL": "Child",
    "ASSO": "Associate",
    "_WITN": "Witness",
}


def _normalize_role_label(tag: str, value: Optional[str]) -> str:
    t = tag.upper()
    if t in _ROLE_LABELS:
        return _ROLE_LABELS[t]
    # Generic: strip leading '_' and title-case
    return t.lstrip("_").title()


def _extract_roles_for_node(node: Dict[str, Any]) -> List[EventRole]:
    """
    Extract role-like children directly under the given node.
    Used for both parent record (FAM/INDI) and event node itself.
    """
    roles: List[EventRole] = []
    for child in node.get("children", []):
        tag = child.get("tag") or ""
        t = tag.upper()
        if _is_role_candidate(t, child):
            val = child.get("pointer") or child.get("value")
            val = _trim(val)
            norm = _normalize_role_label(t, val)
            roles.append(EventRole(tag=t, value=val, normalized=norm))
    return roles


def _merge_roles(*role_lists: List[EventRole]) -> List[EventRole]:
    """
    Merge role lists while preserving order and avoiding exact duplicates.
    """
    seen = set()
    merged: List[EventRole] = []
    for roles in role_lists:
        for r in roles:
            key = (r.tag, r.value)
            if key in seen:
                continue
            seen.add(key)
            merged.append(r)
    return merged


# ---------------------------------------------------------------------------
# Enrichment helpers: cause, certainty, type, description, location, age
# ---------------------------------------------------------------------------

def _extract_cause(node: Dict[str, Any]) -> Optional[str]:
    return _trim(_extract_child_value(node, "CAUS"))


def _extract_certainty(node: Dict[str, Any]) -> Optional[int]:
    raw = _extract_child_value(node, "QUAY")
    if raw is None:
        return None
    try:
        val = int(raw)
    except ValueError:
        return None
    if 0 <= val <= 3:
        return val
    return None


def _normalize_event_type(tag: str) -> str:
    t = (tag or "").upper()
    if t in EVENT_TYPE_MAP:
        return EVENT_TYPE_MAP[t]
    return f"CustomEvent({t})" if t else "Event"


def _extract_description_and_subtype(node: Dict[str, Any], tag: str) -> tuple[Optional[str], Optional[str]]:
    desc: Optional[str] = None
    subtype: Optional[str] = None

    if tag.upper() == "EVEN":
        desc = _trim(node.get("value"))
        subtype = _extract_child_value(node, "TYPE")
    else:
        # For non-EVEN events, TYPE is treated as subtype if present.
        subtype = _extract_child_value(node, "TYPE")

    return desc, subtype


def _parse_coord(raw: Optional[str]) -> Optional[float]:
    if not raw:
        return None
    s = raw.strip().upper()
    if not s:
        return None

    sign = 1.0
    if s[0] in ("N", "S", "E", "W"):
        if s[0] in ("S", "W"):
            sign = -1.0
        s = s[1:].strip()

    # Strip potential degree symbols or extra characters,
    # keeping simple decimal degrees for now.
    s = re.sub(r"[^\d\.\-]+", "", s)
    if not s:
        return None

    try:
        val = float(s)
    except ValueError:
        return None
    return sign * val


def _extract_location(node: Dict[str, Any]) -> Optional[Dict[str, float]]:
    """
    Extract LATI/LONG from a MAP child, if present.
    """
    maps = _extract_child_nodes(node, "MAP")
    if not maps:
        return None

    # Use the first MAP block
    m = maps[0]
    lati = _extract_child_value(m, "LATI")
    longi = _extract_child_value(m, "LONG")

    lat = _parse_coord(lati)
    lon = _parse_coord(longi)

    if lat is None and lon is None:
        return None

    location: Dict[str, float] = {}
    if lat is not None:
        location["latitude"] = lat
    if lon is not None:
        location["longitude"] = lon
    return location if location else None


def _pick_date_info(date_dict: Optional[Dict[str, Any]]) -> Optional[tuple[str, Optional[str], Optional[str]]]:
    """
    From a parse_date dict, pick a usable date string + precision + kind.
    Prefers 'date', falls back to 'start' for ranges.
    """
    if not date_dict:
        return None
    ds = date_dict.get("date") or date_dict.get("start")
    if not ds:
        return None
    return ds, date_dict.get("precision"), date_dict.get("kind")


def _to_date(ds: str) -> Optional[Date]:
    """
    Convert 'YYYY', 'YYYY-MM', or 'YYYY-MM-DD' into a date.
    Missing month/day default to 1 for age estimation.
    """
    if not ds:
        return None
    parts = ds.split("-")
    try:
        year = int(parts[0])
        month = 1
        day = 1
        if len(parts) >= 2:
            month = int(parts[1])
        if len(parts) == 3:
            day = int(parts[2])
        return Date(year, month, day)
    except Exception:
        return None


def _compute_age(birth_info: Optional[Dict[str, Any]], event_info: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Compute approximate age at event given birth and event date dicts from parse_date.
    """
    b = _pick_date_info(birth_info)
    e = _pick_date_info(event_info)
    if not b or not e:
        return None

    b_str, b_prec, b_kind = b
    e_str, e_prec, e_kind = e

    b_dt = _to_date(b_str)
    e_dt = _to_date(e_str)
    if not b_dt or not e_dt:
        return None

    # If event before birth: treat as invalid age
    if e_dt < b_dt:
        return None

    years = e_dt.year - b_dt.year
    months = e_dt.month - b_dt.month
    days = e_dt.day - b_dt.day

    if days < 0:
        months -= 1
        days = None  # don't pretend to know exact days
    if months < 0:
        years -= 1
        months += 12

    # Determine "approximate" flag based on precision/kind
    approximate = False
    if b_prec != "day" or e_prec != "day":
        approximate = True
    if (b_kind and b_kind != "exact") or (e_kind and e_kind != "exact"):
        approximate = True

    if approximate:
        return {
            "years": years,
            "months": None,
            "days": None,
            "approximate": True,
        }

    return {
        "years": years,
        "months": months if months is not None else 0,
        "days": days if days is not None else 0,
        "approximate": False,
    }


# ---------------------------------------------------------------------------
# Core Event Extraction
# ---------------------------------------------------------------------------

def extract_event(
    event_node: Dict[str, Any],
    record_uuid: Optional[str] = None,
    record_node: Optional[Dict[str, Any]] = None,
) -> Event:
    """
    Convert a GEDCOM event node (level 1+ child of INDI/FAM) into a structured Event.
    """
    tag = event_node.get("tag")
    lineno = event_node.get("lineno")
    pointer = event_node.get("pointer")

    # UUID strategy: deterministic, record-scoped
    if record_uuid:
        uuid = f"evt-{record_uuid}-{tag}"
    else:
        uuid = f"evt-{tag}"

    # Roles:
    parent_roles: List[EventRole] = []
    if record_node is not None:
        parent_roles = _extract_roles_for_node(record_node)
    local_roles = _extract_roles_for_node(event_node)
    roles = _merge_roles(parent_roles, local_roles)

    # Basic components
    date_info = _extract_date(event_node)
    place = _extract_place(event_node)
    notes = _extract_notes(event_node)
    sources = _extract_sources(event_node)

    # Enrichment
    cause = _extract_cause(event_node)
    certainty = _extract_certainty(event_node)
    etype = _normalize_event_type(tag or "")
    description, subtype = _extract_description_and_subtype(event_node, tag or "")
    location = _extract_location(event_node)

    # Age at event (for individual records only, non-BIRT)
    age = None
    if record_node is not None and (record_node.get("tag", "").upper() == "INDI") and (tag or "").upper() != "BIRT":
        # Find BIRT in record_node children
        birth_node = None
        for child in record_node.get("children", []):
            if child.get("tag", "").upper() == "BIRT":
                birth_node = child
                break
        if birth_node is not None:
            birth_date = _extract_date(birth_node)
            age = _compute_age(birth_date, date_info)

    return Event(
        uuid=uuid,
        tag=tag,
        date=date_info,
        place=place,
        value=_trim(event_node.get("value")),
        notes=notes,
        sources=sources,
        roles=roles,
        pointer=pointer,
        lineno=lineno,
        type=etype,
        subtype=subtype,
        description=description,
        certainty=certainty,
        cause=cause,
        age=age,
        location=location,
    )


def extract_events_from_record(record_node: Dict[str, Any], record_uuid: Optional[str] = None) -> List[Event]:
    """
    Extract all event nodes from an INDI or FAM record.
    """
    events: List[Event] = []

    for child in record_node.get("children", []):
        tag = child.get("tag", "").upper()
        if is_event_tag(tag):
            events.append(
                extract_event(
                    child,
                    record_uuid=record_uuid,
                    record_node=record_node,
                )
            )

    return events


# ---------------------------------------------------------------------------
# Compatibility API for older modules expecting legacy functions
# ---------------------------------------------------------------------------

def extract_individual_events(children: List[Dict[str, Any]], record_uuid: Optional[str] = None):
    """
    Legacy wrapper preserved for compatibility.
    Extract only individual-typed GEDCOM events from a list of child nodes.
    """
    events = []
    for node in children:
        tag = node.get("tag", "").upper()
        if tag in INDIVIDUAL_EVENT_TAGS:
            events.append(extract_event(node, record_uuid=record_uuid))
    return events


def extract_family_events(children: List[Dict[str, Any]], record_uuid: Optional[str] = None):
    """
    Legacy wrapper preserved for compatibility.
    Extract only family-typed GEDCOM events from a list of child nodes.
    """
    events = []
    for node in children:
        tag = node.get("tag", "").upper()
        if tag in FAMILY_EVENT_TAGS:
            events.append(extract_event(node, record_uuid=record_uuid))
    return events
