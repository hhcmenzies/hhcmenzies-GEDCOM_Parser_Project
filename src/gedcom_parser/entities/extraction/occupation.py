"""
Occupation extraction and normalization utilities.

This module:
- Collects OCCU tag values
- Scans NOTE tag sentences for occupation keywords
- Normalizes all found occupations
- Produces a deduplicated occupation block
"""

from typing import List, Dict
import re


# ---------------------------------------------------------------------
# OCCUPATION NORMALIZATION DICTIONARY
# ---------------------------------------------------------------------

OCCUPATION_MAP = {
    "farmer": ["farmer", "farm laborer", "farmhand"],
    "carpenter": ["carpenter", "carpentry"],
    "clerk": ["clerk", "town clerk", "market clerk"],
    "teacher": ["teacher", "schoolmaster", "school master"],
    "weaver": ["weaver", "linen weaver"],
    "administrator": ["administrator", "manager", "warehouse manager"],
}


# Reverse lookup table for fast keyword matching
REVERSE_LOOKUP = {}
for norm, variants in OCCUPATION_MAP.items():
    for v in variants:
        REVERSE_LOOKUP[v.lower()] = norm


# ---------------------------------------------------------------------
# UTILITIES
# ---------------------------------------------------------------------

def normalize_occ(term: str) -> str:
    """
    Return a normalized occupation form.
    """
    t = term.strip().lower()
    if t in REVERSE_LOOKUP:
        return REVERSE_LOOKUP[t]
    return t  # fallback: raw lower-case term


def extract_from_notes(notes: List[str]) -> List[str]:
    """
    Scan NOTE text for occupation hints using several genealogical patterns.
    """
    occs = []

    # Common occupation keywords (expandable)
    OCC_KEYWORDS = [
        "occupation", "occ", "employed", "employment", "worked",
        "job", "position", "served as", "was a", "was an"
    ]

    # Regex patterns
    patterns = [
        # Occupation: Carpenter
        r"occupation[: ]+([a-zA-Z0-9 \-/,]+)",
        r"occ[: ]+([a-zA-Z0-9 \-/,]+)",

        # Employed as a carpenter
        r"employed as(?: a| an)? ([a-zA-Z0-9 \-]+)",

        # Worked as a carpenter
        r"worked as(?: a| an)? ([a-zA-Z0-9 \-]+)",

        # Worked at the mill as a weaver
        r"worked .* as (?:a|an)? ([a-zA-Z0-9 \-]+)",

        # Served as town clerk
        r"served as(?: a| an)? ([a-zA-Z0-9 \-]+)",

        # "He was a carpenter"
        r"was a ([a-zA-Z0-9 \-]+)",
        r"was an ([a-zA-Z0-9 \-]+)",
    ]

    for note in notes:
        text = note.lower().strip()

        # Try regex patterns
        for pat in patterns:
            m = re.findall(pat, text)
            if m:
                for found in m:
                    # clean multiple possible titles
                    for part in found.split(","):
                        occs.append(part.strip())

        # Direct keyword scanning
        for variant in REVERSE_LOOKUP:
            if variant in text:
                occs.append(variant)

    return occs

    """
    Look for occupation hints inside NOTE values.
    Sentences like "Occupation: Carpenter" or "Worked as a sailor".
    """
    occs = []

    for note in notes:
        text = note.lower()

        # Pattern 1: "Occupation: X"
        m = re.search(r"occupation[: ]+([a-zA-Z ,\-]+)", text)
        if m:
            occupations_text = m.group(1)
            for part in occupations_text.split(","):
                occs.append(part.strip())
            continue

        # Pattern 2: any known occupation keyword inside NOTE
        for variant in REVERSE_LOOKUP:
            if variant in text:
                occs.append(variant)

    return occs


# ---------------------------------------------------------------------
# MAIN EXTRACTION
# ---------------------------------------------------------------------

def extract_occupation_block(occu_values: List[str], note_values: List[str]) -> Dict:
    """
    Build the structured occupation block.

    Example output:
    {
        "all": ["farmer", "clerk"],
        "raw_terms": {
            "OCCU": ["Farmer"],
            "NOTE": ["Occupation: Clerk of the Market"]
        },
        "promoted": ["clerk"]
    }
    """

    raw_occu = occu_values[:]          # original OCCU values
    raw_note = note_values[:]          # NOTE text for scanning

    normalized = []

    # Normalize OCCU tags
    for val in raw_occu:
        for part in val.split(","):
            cleaned = part.strip()
            if cleaned:
                normalized.append(normalize_occ(cleaned))

    # Extract from NOTE text
    inferred = extract_from_notes(raw_note)
    inferred_norm = [normalize_occ(x) for x in inferred]

    promoted = []

    # Add inferred occupations that are not already present
    for term in inferred_norm:
        if term not in normalized:
            normalized.append(term)
            promoted.append(term)

    # Deduplicate
    normalized = sorted(set(normalized))

    return {
        "all": normalized,
        "raw_terms": {
            "OCCU": raw_occu,
            "NOTE": raw_note,
        },
        "promoted": promoted,
    }
