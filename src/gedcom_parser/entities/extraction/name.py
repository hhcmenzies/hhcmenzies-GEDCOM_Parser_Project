"""
Clean, upgraded NAME parser (C.24.4.2 + C.24.4.3)

Outputs a fully normalized block:

{
    "prefix": str|None,
    "given": str|None,
    "middle": [str],
    "surname_prefix": str|None,
    "surname": str|None,
    "suffix": str|None,
    "full": str,                     # raw GEDCOM NAME string
    "full_name_normalized": str,     # reconstructed canonical form
    "romanized": None,
    "phonetic": None,
    "alias": None,
}

Used by:
- extractor.py
- name_identity.py
- uuid_factory.py
"""

from __future__ import annotations
from typing import Any, Dict, List

from gedcom_parser.entities.extraction.name_normalization import (
    detect_prefix,
    detect_suffix,
    detect_surname_prefix,
)


# ==========================================================
# PRIMARY PARSER
# ==========================================================

def parse_name_value(name_value: str) -> Dict[str, Any]:
    """
    Parse a GEDCOM NAME value:

        "Given Middle /Surname/"
        "Dr. David Allen /Sargent/ Jr."
        "/Colleen/"
        "Jean /de la Fontaine/"

    Minimal assumptions; GEDCOM is often messy.

    Returns a complete normalized block.
    """

    raw = name_value or ""
    surname = None
    left = raw

    # -------------------------------
    # Split surname if slashes exist
    # -------------------------------
    if "/" in raw:
        left, _, right = raw.partition("/")
        surname = right.strip() or None

    # Tokenize left side
    tokens = [t for t in left.strip().split(" ") if t]

    # -------------------------------
    # Prefix (Dr., Mr., Mrs., Rev., etc.)
    # -------------------------------
    prefix = detect_prefix(tokens)
    if prefix:
        tokens = tokens[1:]

    # -------------------------------
    # Suffix (Jr., Sr., III, Esq., etc.)
    # -------------------------------
    suffix = detect_suffix(tokens)
    if suffix:
        tokens = tokens[:-1]

    # -------------------------------
    # Surname prefix (de, van, von, ap, mac, etc.)
    # -------------------------------
    surname_prefix = detect_surname_prefix(tokens)
    if surname_prefix:
        sp_len = len(surname_prefix.split(" "))
        tokens = tokens[sp_len:]

    # -------------------------------
    # Remaining tokens: given + middle
    # -------------------------------
    given = tokens[0] if tokens else None
    middle = tokens[1:] if len(tokens) > 1 else []

    # -------------------------------
    # Build normalized full name
    # -------------------------------
    parts = []
    if prefix:
        parts.append(prefix)
    if given:
        parts.append(given)
    parts.extend(middle)
    if surname_prefix:
        parts.append(surname_prefix)
    if surname:
        parts.append(surname)
    if suffix:
        parts.append(suffix)

    normalized = " ".join(parts).strip()

    return {
        "prefix": prefix,
        "given": given,
        "middle": middle,
        "surname_prefix": surname_prefix,
        "surname": surname,
        "suffix": suffix,
        "full": raw,
        "full_name_normalized": normalized,
        "romanized": None,
        "phonetic": None,
        "alias": None,
    }


# ==========================================================
# MERGE NAME-TAG CHILDREN
# ==========================================================

def merge_name_tags(base: Dict[str, Any],
                    children: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Merge NAME-level GEDCOM sub-tags:

        NPFX / GIVN / SPFX / SURN / NSFX / ROMN / FONE / NICK

    Child tags override parsed values where appropriate.

    Does NOT assign UUID. extractor.py does that.
    """

    out = dict(base)

    for ch in children:
        tag = ch.get("tag")
        val = (ch.get("value") or "").strip()
        if not tag:
            continue

        if tag == "NPFX":
            out["prefix"] = val or out.get("prefix")

        elif tag == "GIVN":
            # Replace given + middle with a single composite if provided
            parts = val.split()
            out["given"] = parts[0] if parts else out.get("given")
            out["middle"] = parts[1:] if len(parts) > 1 else []

        elif tag == "SPFX":
            out["surname_prefix"] = val

        elif tag == "SURN":
            out["surname"] = val or out.get("surname")

        elif tag == "NSFX":
            out["suffix"] = val or out.get("suffix")

        elif tag == "ROMN":
            out["romanized"] = val

        elif tag == "FONE":
            out["phonetic"] = val

        elif tag == "NICK":
            out["alias"] = val

    # Rebuild normalized full name
    parts = []
    if out.get("prefix"):
        parts.append(out["prefix"])
    if out.get("given"):
        parts.append(out["given"])
    if out.get("middle"):
        parts.extend(out["middle"])
    if out.get("surname_prefix"):
        parts.append(out["surname_prefix"])
    if out.get("surname"):
        parts.append(out["surname"])
    if out.get("suffix"):
        parts.append(out["suffix"])

    out["full_name_normalized"] = " ".join(p for p in parts if p).strip()

    return out
