"""
GEDCOM Line Tokenizer
---------------------

Converts raw GEDCOM lines into structured token dictionaries.

A GEDCOM line has the format:

    <level> <optional pointer> <tag> <optional value>

Examples:
    0 @I1@ INDI
    1 NAME John /Doe/
    2 DATE 1 JAN 1900
"""

import re
from typing import Optional, Dict

GEDCOM_LINE_RE = re.compile(
    r"^(?P<level>\d+)\s+"
    r"(?:(?P<pointer>@[^@]+@)\s+)?"
    r"(?P<tag>[A-Z0-9_]+)"
    r"(?:\s+(?P<value>.+))?$"
)


def tokenize_line(line: str) -> Optional[Dict]:
    """Tokenize a single GEDCOM line into components."""
    line = line.strip()
    if not line:
        return None

    match = GEDCOM_LINE_RE.match(line)
    if not match:
        return None

    return {
        "level": int(match.group("level")),
        "pointer": match.group("pointer"),
        "tag": match.group("tag"),
        "value": match.group("value") or ""
    }


def tokenize_file(path: str):
    """Yield token dictionaries for each valid GEDCOM line."""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for lineno, raw_line in enumerate(f, 1):
            token = tokenize_line(raw_line)
            if token:
                token["lineno"] = lineno
                yield token
