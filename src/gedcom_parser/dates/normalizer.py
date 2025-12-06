"""
Date normalization helpers for GEDCOM-style date strings.

Goal:
- Accept raw GEDCOM-ish date strings (e.g. "Abt. 1694", "BET 1690 AND 1695",
  "14 Jul 1684", "1699", etc.).
- Return a structured dict with:
    - raw: original input
    - kind: classification ("simple", "about", "before", "after",
      "between", "from_to", "range", "unknown")
    - normalized: single ISO-like date when reasonable (YYYY-MM-DD)
    - start / end: range boundaries where applicable
    - year / month / day fields when parseable

This is deliberately conservative: if we cannot safely interpret,
we fall back to kind="unknown" and leave normalized/start/end as None.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple

# Basic English month mapping. We can extend later if needed.
_MONTHS = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "SEPT": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}

_WHITESPACE_RE = re.compile(r"\s+")


def _clean(s: str) -> str:
    return _WHITESPACE_RE.sub(" ", s.strip())


def _iso_date(year: int, month: Optional[int] = None, day: Optional[int] = None) -> str:
    """
    Build a simple ISO-like date string.
    If month/day are missing, we default month=1, day=1 so the value
    can be used as a range boundary.
    """
    if month is None:
        month = 1
    if day is None:
        day = 1
    return f"{year:04d}-{month:02d}-{day:02d}"


def _parse_simple_date(raw: str) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    """
    Parse simple styles like:
    - "1699"
    - "14 Jul 1684"
    - "Jul 1684"
    - "1684-07-14" (ISO-ish, tolerant)
    """
    s = _clean(raw)

    # ISO-like "YYYY-MM-DD"
    iso_match = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", s)
    if iso_match:
        y, m, d = iso_match.groups()
        return int(y), int(m), int(d)

    # Day Month Year (14 Jul 1684 / 14 July 1684)
    dmy_match = re.match(
        r"^(\d{1,2})\s+([A-Za-z]{3,})\.?,?\s+(\d{3,4})$", s
    )
    if dmy_match:
        d, mon_str, y = dmy_match.groups()
        mon = _MONTHS.get(mon_str[:3].upper())
        if mon and y.isdigit():
            return int(y), mon, int(d)

    # Month Year (Jul 1684 / July 1684)
    my_match = re.match(
        r"^([A-Za-z]{3,})\.?,?\s+(\d{3,4})$", s
    )
    if my_match:
        mon_str, y = my_match.groups()
        mon = _MONTHS.get(mon_str[:3].upper())
        if mon and y.isdigit():
            return int(y), mon, None

    # Year only
    if s.isdigit() and len(s) in (3, 4):
        return int(s), None, None

    # Dual year style "1699/00" etc. For now we treat as the first year.
    dual_match = re.match(r"^(\d{3,4})/\d{2}$", s)
    if dual_match:
        y = dual_match.group(1)
        return int(y), None, None

    return None, None, None


def parse_gedcom_date(raw: str) -> Dict[str, Any]:
    """
    Main public entry:
        parse_gedcom_date("Abt. 1694") -> structured dict

    Does NOT try to be fully locale-aware. It aims for:
    - Stable classification (kind).
    - Reasonable normalization when safe.
    - Non-destructive fallback when ambiguous.
    """
    if raw is None:
        return {
            "raw": None,
            "kind": "unknown",
            "normalized": None,
            "start": None,
            "end": None,
            "year": None,
            "month": None,
            "day": None,
        }

    s = _clean(raw).upper()

    result: Dict[str, Any] = {
        "raw": raw,
        "kind": "unknown",
        "normalized": None,
        "start": None,
        "end": None,
        "year": None,
        "month": None,
        "day": None,
    }

    # ABOUT: ABT, ABT., ABOUT, EST, CALC, CAL
    if s.startswith(("ABT ", "ABT.", "ABOUT ", "EST ", "EST.", "CALC ", "CALC.", "CAL ")):
        # Strip prefix and parse remainder as a simple date.
        stripped = re.sub(r"^(ABT\.?|ABOUT|EST\.?|CALC\.?|CAL)\s+", "", s)
        y, m, d = _parse_simple_date(stripped)
        if y is not None:
            result["kind"] = "about"
            result["year"] = y
            result["month"] = m
            result["day"] = d
            result["normalized"] = _iso_date(y, m, d)
            return result

    # AFTER: AFT, AFT., AFTER
    if s.startswith(("AFT ", "AFT.", "AFTER ")):
        stripped = re.sub(r"^(AFT\.?|AFTER)\s+", "", s)
        y, m, d = _parse_simple_date(stripped)
        if y is not None:
            result["kind"] = "after"
            result["year"] = y
            result["month"] = m
            result["day"] = d
            result["start"] = _iso_date(y, m, d)
            # end left open
            return result

    # BEFORE: BEF, BEF., BEFORE
    if s.startswith(("BEF ", "BEF.", "BEFORE ")):
        stripped = re.sub(r"^(BEF\.?|BEFORE)\s+", "", s)
        y, m, d = _parse_simple_date(stripped)
        if y is not None:
            result["kind"] = "before"
            result["year"] = y
            result["month"] = m
            result["day"] = d
            # start left unspecified, end is boundary
            result["end"] = _iso_date(y, m, d)
            return result

    # BETWEEN / AND (BET 1690 AND 1695)
    bet_match = re.match(r"^BET\s+(.+)\s+AND\s+(.+)$", s)
    if bet_match:
        left_raw, right_raw = bet_match.groups()
        y1, m1, d1 = _parse_simple_date(left_raw)
        y2, m2, d2 = _parse_simple_date(right_raw)
        if y1 is not None and y2 is not None:
            result["kind"] = "between"
            result["start"] = _iso_date(y1, m1, d1)
            result["end"] = _iso_date(y2, m2, d2)
            # no single normalized point; this is a range.
            return result

    # FROM / TO (FROM 1690 TO 1695)
    from_match = re.match(r"^FROM\s+(.+)\s+TO\s+(.+)$", s)
    if from_match:
        left_raw, right_raw = from_match.groups()
        y1, m1, d1 = _parse_simple_date(left_raw)
        y2, m2, d2 = _parse_simple_date(right_raw)
        if y1 is not None and y2 is not None:
            result["kind"] = "from_to"
            result["start"] = _iso_date(y1, m1, d1)
            result["end"] = _iso_date(y2, m2, d2)
            return result

    # Simple date case, no qualifiers
    y, m, d = _parse_simple_date(raw)
    if y is not None:
        result["kind"] = "simple"
        result["year"] = y
        result["month"] = m
        result["day"] = d
        result["normalized"] = _iso_date(y, m, d)
        return result

    # If we get here, we could not parse safely.
    # We keep kind="unknown" but preserve raw.
    return result
