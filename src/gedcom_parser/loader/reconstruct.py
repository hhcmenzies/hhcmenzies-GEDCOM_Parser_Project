# src/gedcom_parser/loader/reconstruct.py

"""
Reconstruct multi-line GEDCOM values from CONC / CONT records.

This module provides `reconstruct_values`, which takes a flat list of
token dicts (as produced by `tokenize_file`) and merges any CONC/CONT
records into the previous *non-CONC/CONT* token's `value`.

- CONC → concatenates directly (no newline)
- CONT → concatenates with a newline between lines

The function is pure: it returns a new list and does not mutate the
input tokens.
"""

from __future__ import annotations

from typing import Any, Dict, List


Token = Dict[str, Any]


def reconstruct_values(tokens: List[Token]) -> List[Token]:
    """
    Given a list of token dictionaries:

        {"level": int, "tag": str, "value": str, ...}

    merge sequences of CONC / CONT tokens into the previous non-CONC/CONT
    token, updating that token's `value` field.

    Example:
        1 NOTE First line
        2 CONC continued
        2 CONT next line

    becomes:
        1 NOTE "First linecontinued\nnext line"

    Returns a *new* list of tokens.
    """
    if not tokens:
        return []

    out: List[Token] = []

    for tok in tokens:
        tag = str(tok.get("tag", "")).upper()
        value = tok.get("value") or ""

        if tag in ("CONC", "CONT") and out:
            base = out[-1]

            # only merge into a token that is not itself CONC/CONT
            base_tag = str(base.get("tag", "")).upper()
            if base_tag in ("CONC", "CONT"):
                # If somehow we got a CONC/CONT at the end, just treat it as
                # a normal token to avoid losing data.
                out.append(dict(tok))
                continue

            existing = base.get("value") or ""
            if tag == "CONC":
                base["value"] = existing + value
            else:  # CONT
                # Newline between lines as per GEDCOM semantics
                if existing:
                    base["value"] = existing + "\n" + value
                else:
                    base["value"] = value
        else:
            # Normal token → copy it into output
            out.append(dict(tok))

    return out
