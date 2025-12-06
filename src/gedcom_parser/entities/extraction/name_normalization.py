"""
Name normalization utilities used by name.py.

C.24.4.2 / C.24.4.3:
- Detects prefix (NPFX)
- Detects suffix (NSFX)
- Detects surname_prefix (SPFX-like elements)
- Uses expandable dictionaries that can be replaced/extended
  via external datasets at C.24.4.9
"""

from __future__ import annotations
from typing import List, Optional


# ==========================================================
# CANONICAL PREFIX / SUFFIX / SURNAME_PREFIX TABLES
# (Universally safe defaults — full datasets added in C.24.4.9)
# ==========================================================

# Titles, honorifics, ecclesiastical ranks, nobility, common prefixes
PREFIXES = {
    "mr", "mr.", "mister",
    "mrs", "mrs.", "misses",
    "ms", "ms.",
    "miss",
    "dr", "dr.", "doctor",
    "prof", "prof.",
    "rev", "rev.", "reverend",
    "sir", "lord", "lady",
    "hon", "hon.",
    "fr", "fr.",
    "sr", "sr.",
}

# Canonical suffixes (name endings)
SUFFIXES = {
    "jr", "jr.", "sr", "sr.",
    "ii", "iii", "iv", "v",
    "esq", "esq.",
    "phd", "m.d.", "md", "jd",
}

# Multilingual surname prefixes
# NOTE: Larger datasets will be added later.
SURNAME_PREFIXES = [
    "de", "du", "del", "della",
    "van", "von", "der", "den",
    "la", "le",
    "de la", "de las", "de los",
    "van de", "van der", "von der", "von dem",
    "ap", "ab",
    "mac", "mc",
]


# ==========================================================
# HELPERS
# ==========================================================

def _normalize(s: Optional[str]) -> str:
    """Lowercase and strip punctuation for matching."""
    if not s:
        return ""
    return s.lower().strip().replace(",", "").replace(".", "")


# ==========================================================
# PREFIX DETECTION
# ==========================================================

def detect_prefix(tokens: List[str]) -> Optional[str]:
    """
    Return the first token if it is a known name prefix.
    """
    if not tokens:
        return None

    candidate = _normalize(tokens[0])
    return tokens[0] if candidate in PREFIXES else None


# ==========================================================
# SUFFIX DETECTION
# ==========================================================

def detect_suffix(tokens: List[str]) -> Optional[str]:
    """
    Return the last token if it is a known suffix.
    """
    if not tokens:
        return None

    candidate = _normalize(tokens[-1])
    return tokens[-1] if candidate in SUFFIXES else None


# ==========================================================
# SURNAME PREFIX DETECTION
# ==========================================================

def detect_surname_prefix(tokens: List[str]) -> Optional[str]:
    """
    Detect single or multi-word surname prefixes.

    Examples:
        "de la Fontaine" → "de la"
        "van der Berg"  → "van der"
        "von"           → "von"
        "Mac Donald"    → "Mac"
        "ap Owen"       → "ap"
    """

    if not tokens:
        return None

    # Join progressively increasing sequences:
    # 1 token → 2 tokens → 3 tokens → ...
    lowered = [_normalize(t) for t in tokens]

    # Check longest possible surname prefix first
    for length in range(min(3, len(tokens)), 0, -1):
        segment = " ".join(lowered[:length])
        if segment in SURNAME_PREFIXES:
            # Return the original-case tokens
            return " ".join(tokens[:length])

    return None
