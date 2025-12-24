# src/gedcom_parser/dates/normalizer.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple, List


# ---------------------------------------------------------------------------
# Month and calendar helpers
# ---------------------------------------------------------------------------

MONTHS = {
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

CALENDAR_ALIASES = {
    "JULIAN": "JULIAN",
    "OLD STYLE": "JULIAN",
    "GREGORIAN": "GREGORIAN",
    "NEW STYLE": "GREGORIAN",
}


# ---------------------------------------------------------------------------
# Qualifier / modifier mapping based on date_normalization.json
# ---------------------------------------------------------------------------

# Each entry: alias (lowercase) -> (standard_code, kind)
QUALIFIER_ALIASES: Dict[str, Tuple[str, str]] = {}

def _add_qualifier_aliases(aliases: List[str], code: str, kind: str) -> None:
    for a in aliases:
        QUALIFIER_ALIASES[a.lower()] = (code, kind)


# Approximate: ABT
_add_qualifier_aliases(
    [
        "abt",
        "abt.",
        "about",
        "approx",
        "approx.",
        "approximately",
        "circa",
        "c",
        "c.",
        "around",
        "ca",
        "ca.",
    ],
    "ABT",
    "approximate",
)

# Before: BEF
_add_qualifier_aliases(
    [
        "before",
        "bef",
        "bef.",
        "previous to",
        "prior to",
        "pre",
        "pre-",
        "earlier than",
    ],
    "BEF",
    "before",
)

# After: AFT
_add_qualifier_aliases(
    [
        "after",
        "aft",
        "aft.",
        "post",
        "post-",
        "afterwards",
        "later than",
    ],
    "AFT",
    "after",
)

# Between: BET (range)
_add_qualifier_aliases(
    [
        "between",
        "bet",
        "bet.",
        "betw",
        "betw.",
        "btw",
        "btw.",
        "ranging from",
    ],
    "BET",
    "range",
)

# Calculated: CAL
_add_qualifier_aliases(
    [
        "cal",
        "cal.",
        "calculated",
        "computed",
        "computed from",
    ],
    "CAL",
    "calculated",
)

# Estimated: EST
_add_qualifier_aliases(
    [
        "est",
        "est.",
        "estimated",
        "estimate",
        "guess",
        "guessed",
        "roughly",
        "probable",
        "assumed",
    ],
    "EST",
    "estimated",
)

# FROM
_add_qualifier_aliases(
    [
        "from",
        "since",
    ],
    "FROM",
    "range_start",
)

# TO
_add_qualifier_aliases(
    [
        "to",
        "until",
        "thru",
        "through",
    ],
    "TO",
    "range_end",
)

# BETWEEN / AND will be treated in parsing logic; we keep "BET" via aliases.


# Seasonal references
SEASON_ALIASES: Dict[str, str] = {
    "spring": "SPRING",
    "summer": "SUMMER",
    "autumn": "AUTUMN",
    "fall": "AUTUMN",
    "winter": "WINTER",
}

EARLY_MID_LATE = {"early", "mid", "late"}


@dataclass
class ParsedSimpleDate:
    """Internal helper for a single date portion (no qualifier)."""
    date: Optional[str]          # normalized date string (YYYY, YYYY-MM, YYYY-MM-DD)
    precision: Optional[str]     # 'year', 'month', 'day'
    kind: str                    # 'exact', 'seasonal', 'unknown'
    season: Optional[str] = None # SPRING, SUMMER, AUTUMN, WINTER, if seasonal
    year: Optional[int] = None


# ---------------------------------------------------------------------------
# Core parsing helpers
# ---------------------------------------------------------------------------

def _strip_calendar_suffix(raw: str) -> Tuple[str, Optional[str]]:
    """
    Remove a trailing '(CalendarName)' suffix if present, return (base, calendar).
    """
    s = raw.strip()
    calendar = None

    if s.endswith(")"):
        # crude but effective: look for last '('
        idx = s.rfind("(")
        if idx != -1:
            label = s[idx + 1 : -1].strip()
            base = s[:idx].strip()
            cal = CALENDAR_ALIASES.get(label.upper())
            if cal:
                calendar = cal
                s = base

    return s, calendar


def _parse_year(token: str) -> Optional[int]:
    token = token.strip()
    if len(token) == 4 and token.isdigit():
        return int(token)
    # allow 3-digit "year" for deep history
    if len(token) == 3 and token.isdigit():
        return int(token)
    return None


def _parse_simple_date(text: str) -> ParsedSimpleDate:
    """
    Parse a date with no leading qualifiers (ABT, BEF, BET, etc. removed already).

    Supports:
        - '1900'
        - 'JAN 1900'
        - '1 JAN 1900'
        - 'spring 1880'
        - 'early 1800s', 'mid 1820s', 'late 1700s' → treated as 'unknown' kind here;
          range semantics are handled at a higher level if needed later.
    """
    s = text.strip()
    if not s:
        return ParsedSimpleDate(date=None, precision=None, kind="unknown")

    tokens = s.replace(",", " ").split()
    tokens = [t for t in tokens if t]  # remove empties

    # Seasonal: 'spring 1880'
    if len(tokens) == 2 and tokens[0].lower() in SEASON_ALIASES:
        season = SEASON_ALIASES[tokens[0].lower()]
        year = _parse_year(tokens[1])
        if year is not None:
            # We keep date at year-level, but mark as seasonal.
            return ParsedSimpleDate(
                date=str(year),
                precision="year",
                kind="seasonal",
                season=season,
                year=year,
            )

    # "early/mid/late 1800s" - for now we just normalize the year token and
    # treat as 'unknown' kind, leaving more exact range semantics for later.
    if len(tokens) == 2 and tokens[0].lower() in EARLY_MID_LATE:
        year_token = tokens[1].rstrip("s")  # '1800s' -> '1800'
        year = _parse_year(year_token)
        if year is not None:
            return ParsedSimpleDate(
                date=str(year),
                precision="year",
                kind="unknown",
                year=year,
            )

    # 1 token → year?
    if len(tokens) == 1:
        year = _parse_year(tokens[0])
        if year is not None:
            return ParsedSimpleDate(
                date=f"{year:04d}",
                precision="year",
                kind="exact",
                year=year,
            )
        # Unknown single token
        return ParsedSimpleDate(date=None, precision=None, kind="unknown")

    # 2 tokens → either 'MON YYYY' or something else
    if len(tokens) == 2:
        # Try MON YYYY
        mon_token, year_token = tokens
        year = _parse_year(year_token)
        mon = MONTHS.get(mon_token.upper())
        if year is not None and mon is not None:
            return ParsedSimpleDate(
                date=f"{year:04d}-{mon:02d}",
                precision="month",
                kind="exact",
                year=year,
            )
        # Unknown pattern
        return ParsedSimpleDate(date=None, precision=None, kind="unknown")

    # >= 3 tokens → try 'DD MON YYYY'
    # Allow things like '1 JAN 1900', '01 JAN 1900'
    day_token, mon_token, year_token = tokens[0], tokens[1], tokens[2]
    year = _parse_year(year_token)
    mon = MONTHS.get(mon_token.upper())
    if year is not None and mon is not None and day_token.isdigit():
        day = int(day_token)
        # We don't validate day range strictly here; assume caller sanitized.
        return ParsedSimpleDate(
            date=f"{year:04d}-{mon:02d}-{day:02d}",
            precision="day",
            kind="exact",
            year=year,
        )

    # Fallback
    return ParsedSimpleDate(date=None, precision=None, kind="unknown")


def _split_on(tokens: List[str], separators: List[str]) -> Optional[Tuple[List[str], List[str]]]:
    """
    Split tokens into (left, right) at the first occurrence of any separator token
    (case-insensitive). Returns None if no separator found.
    """
    lowers = [s.lower() for s in separators]
    for i, t in enumerate(tokens):
        if t.lower() in lowers:
            left = tokens[:i]
            right = tokens[i + 1 :]
            return left, right
    return None


# ---------------------------------------------------------------------------
# Main public API
# ---------------------------------------------------------------------------

def parse_date(raw: str) -> Dict[str, Optional[str]]:
    """
    Parse a GEDCOM DATE value into a structured dictionary.

    Hybrid precision behavior:
        - '1 JAN 1900'   -> normalized='1900-01-01', precision='day'
        - 'JAN 1900'     -> normalized='1900-01',    precision='month'
        - '1900'         -> normalized='1900',       precision='year'

    Qualifiers such as ABT, BEF, AFT, BET, FROM, TO are recognized using
    the qualifier alias map derived from the date_normalization.json dataset.

    Returns a dict with keys:
        raw         : original input (stripped)
        normalized  : canonical normalized string (see above)
        kind        : 'exact', 'approximate', 'before', 'after', 'range',
                      'calculated', 'estimated', 'seasonal', 'unknown'
        modifier    : standardized modifier (ABT, BEF, AFT, BET, CAL, EST, FROM, TO) or None
        date        : normalized simple date if applicable (string) or None
        precision   : 'day', 'month', 'year', or None
        start       : for ranges, normalized start date (string) or None
        end         : for ranges, normalized end date (string) or None
        calendar    : 'GREGORIAN', 'JULIAN', or None
        season      : for seasonal dates, e.g. 'SPRING', else None
    """
    if raw is None:
        s = ""
    else:
        s = str(raw).strip()

    result: Dict[str, Optional[str]] = {
        "raw": s,
        "normalized": s,
        "kind": "unknown",
        "modifier": None,
        "date": None,
        "precision": None,
        "start": None,
        "end": None,
        "calendar": None,
        "season": None,
    }

    if not s:
        return result

    # Calendar suffix, e.g. "1 JAN 1750 (Julian)"
    base, calendar = _strip_calendar_suffix(s)
    if calendar:
        result["calendar"] = calendar

    # Tokenize the base date string
    tokens = base.replace(",", " ").split()
    tokens = [t for t in tokens if t]

    if not tokens:
        return result

    # ------------------------------------------------------------------
    # Range patterns first: BET ... AND ..., FROM ... TO ...
    # ------------------------------------------------------------------
    first_lower = tokens[0].lower()

    # BETWEEN / BET range (BET <date1> AND <date2>)
    if first_lower in ("bet", "between", "btw", "betw", "ranging", "ranging from"):
        # remove first token and split on 'AND'
        rest = tokens[1:]
        split = _split_on(rest, ["and"])
        if split:
            left_tokens, right_tokens = split
            left_text = " ".join(left_tokens)
            right_text = " ".join(right_tokens)
            left = _parse_simple_date(left_text)
            right = _parse_simple_date(right_text)
            result["kind"] = "range"
            result["modifier"] = "BET"
            result["start"] = left.date
            result["end"] = right.date
            result["normalized"] = base
            return result

    # FROM ... TO ... range
    if first_lower in ("from", "since"):
        rest = tokens[1:]
        split = _split_on(rest, ["to", "until", "thru", "through"])
        if split:
            left_tokens, right_tokens = split
            left_text = " ".join(left_tokens)
            right_text = " ".join(right_tokens)
            left = _parse_simple_date(left_text)
            right = _parse_simple_date(right_text)
            result["kind"] = "range"
            result["modifier"] = "FROM"
            result["start"] = left.date
            result["end"] = right.date
            result["normalized"] = base
            return result

    # ------------------------------------------------------------------
    # Single leading qualifier (ABT, BEF, AFT, CAL, EST, etc.)
    # ------------------------------------------------------------------
    modifier_code: Optional[str] = None
    modifier_kind: Optional[str] = None
    remaining_tokens = tokens[:]

    head = remaining_tokens[0].lower()
    if head in QUALIFIER_ALIASES:
        modifier_code, modifier_kind = QUALIFIER_ALIASES[head]
        remaining_tokens = remaining_tokens[1:]

    # If we consumed all tokens, we can't parse an actual date – return with modifier info.
    if not remaining_tokens:
        result["kind"] = modifier_kind or "unknown"
        result["modifier"] = modifier_code
        result["normalized"] = base
        return result

    # Seasonal dates starting with a season term
    if remaining_tokens[0].lower() in SEASON_ALIASES:
        season_text = " ".join(remaining_tokens)
        sd = _parse_simple_date(season_text)
        result["normalized"] = base
        result["kind"] = "seasonal"
        result["modifier"] = modifier_code
        result["date"] = sd.date
        result["precision"] = sd.precision
        result["season"] = sd.season
        return result

    # Plain simple date (no range, maybe with modifier)
    simple_text = " ".join(remaining_tokens)
    sd = _parse_simple_date(simple_text)

    result["date"] = sd.date
    result["precision"] = sd.precision
    result["normalized"] = sd.date or base
    result["kind"] = modifier_kind or sd.kind
    result["modifier"] = modifier_code

    return result
