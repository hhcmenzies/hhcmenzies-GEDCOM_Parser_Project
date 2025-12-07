"""
C.24.4.10 - Name Normalization (Hybrid Parser + NameBlock)

This module is currently a MANUAL post-process step:

    export PYTHONPATH=./src

    python -m gedcom_parser.normalization.name_normalization \
        -i outputs/export_xref.json \
        -o outputs/export_names_normalized.json \
        --debug

Responsibilities:
- Walk all individuals in a registry JSON.
- For each primary NAME:
    * Preserve the raw NAME string.
    * Use GEDCOM child tags (GIVN, SURN, NICK, NPFX, NSFX, SPFX, TITL) when present.
    * ALSO parse the raw NAME line to recover tokens exporters miss.
- Build a structured NameBlock {
      raw,
      uuid,
      parsed: ParsedName,
      normalized: NormalizedName
  }
- Attach NameBlock under each individual:

    individuals[indi_id]["name_block"] = <dict>

Later:
- This will be integrated into the main export pipeline.
- Entity resolution will use the normalized name blocks for scoring.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from gedcom_parser.logging import get_logger
from gedcom_parser.entities.name_block import (
    NameBlock,
    ParsedName,
    NormalizedName,
)

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def safe_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", safe_str(text)).strip()


# A very permissive noise filter: keep letters, digits, spaces, some punctuation.
# We drop emoji and other odd symbols.
NOISE_KEEP_RE = re.compile(r"[A-Za-z0-9\s'\"()/\-,.]+")


def strip_noise_chars(text: str) -> str:
    if not text:
        return ""
    # Take only characters that match our allowed set
    kept = "".join(ch for ch in text if NOISE_KEEP_RE.match(ch))
    # Fallback: if we stripped everything, return the original
    if not kept.strip():
        return text
    return normalize_whitespace(kept)


def normalize_case(token: str) -> str:
    token = token.strip()
    if not token:
        return token
    # If all uppercase or mixed weirdly, fall back to title-case-ish
    if token.isupper():
        return token.title()
    # For surnames with prefixes (e.g., "van der Meer") we rely on later logic.
    return token


# ---------------------------------------------------------------------------
# GEDCOM NAME parsing
# ---------------------------------------------------------------------------


def extract_name_children(name_children: Iterable[Dict[str, Any]]) -> Dict[str, str]:
    """
    From a list of NAME child nodes (raw_children) extract key GEDCOM tags:
    NPFX, GIVN, NICK, SPFX, SURN, NSFX, TITL, TYPE, ROMN, FONE, AKA, etc.

    Returns a dict[str, str] with lowercase keys and raw values.
    """
    result: Dict[str, str] = {}
    for child in name_children or []:
        tag = safe_str(child.get("tag")).upper()
        value = safe_str(child.get("value"))
        if not tag or not value:
            continue

        # Only take first instance per tag (for now)
        if tag in ("NPFX", "GIVN", "NICK", "SPFX", "SURN", "NSFX", "TITL", "TYPE", "ROMN", "FONE", "AKA"):
            result[tag.lower()] = value

    return result


def parse_raw_name_line(raw_name: str) -> Tuple[
    str, List[str], Optional[str], Optional[str], Optional[str], Optional[str], Optional[str], List[str], List[str], List[str]
]:
    """
    Parse the raw GEDCOM NAME line, e.g.:

        "David Thomas /Menzies/"
        "Mary (Smith) \"Polly\" /Jones/"

    Returns:
        given: str
        middle_tokens: list[str]
        surname_prefix: Optional[str]
        surname: Optional[str]
        suffix: Optional[str]
        nickname: Optional[str]
        maiden_name: Optional[str]
        additional_tokens: list[str]
        notes: list[str]
        warnings: list[str]
    """

    raw = safe_str(raw_name)
    raw = normalize_whitespace(raw)

    notes: List[str] = []
    warnings: List[str] = []
    additional_tokens: List[str] = []

    # Extract quoted nicknames: "Polly"
    nickname: Optional[str] = None
    quote_match = re.search(r'["“”](.+?)["“”]', raw)
    if quote_match:
        nickname = normalize_case(quote_match.group(1))
        raw = raw.replace(quote_match.group(0), " ")

    # Extract parentheses contents (often maiden names or nicknames)
    maiden_name: Optional[str] = None
    paren_matches = re.findall(r"\(([^)]+)\)", raw)
    if paren_matches:
        # Use first as maiden-name candidate; others become notes
        maiden_candidate = normalize_case(paren_matches[0])
        maiden_name = maiden_candidate
        if len(paren_matches) > 1:
            notes.append(f"Extra parentheses tokens: {paren_matches[1:]}")
        # Remove parentheses from raw
        raw = re.sub(r"\([^)]+\)", " ", raw)

    # Strip noise characters
    raw_clean = strip_noise_chars(raw)

    # GEDCOM slash convention: given-names before '/', surname between '/', suffix after.
    # Example: "David Thomas /Menzies/" or "John /van der Meer/"
    given_part = raw_clean
    surname_part = ""
    suffix_part = ""

    if "/" in raw_clean:
        parts = raw_clean.split("/")
        if len(parts) >= 2:
            given_part = parts[0].strip()
            surname_part = parts[1].strip()
            if len(parts) >= 3:
                suffix_part = parts[2].strip()

    given_part = normalize_whitespace(given_part)
    surname_part = normalize_whitespace(surname_part)
    suffix_part = normalize_whitespace(suffix_part)

    # Split given_part into tokens: first token is given, rest are middle
    given_tokens = [t for t in given_part.split(" ") if t]
    given = ""
    middle_tokens: List[str] = []

    if given_tokens:
        given = normalize_case(given_tokens[0])
        if len(given_tokens) > 1:
            middle_tokens = [normalize_case(t) for t in given_tokens[1:]]

    # Try to split surname prefix vs surname proper
    surname_prefix: Optional[str] = None
    surname = None
    if surname_part:
        sur_tokens = [t for t in surname_part.split(" ") if t]
        if len(sur_tokens) > 1 and sur_tokens[0].lower() in {"van", "von", "de", "del", "della", "da", "mac", "mc"}:
            surname_prefix = normalize_case(sur_tokens[0])
            surname = normalize_case(" ".join(sur_tokens[1:]))
        else:
            surname = normalize_case(" ".join(sur_tokens))

    suffix = normalize_case(suffix_part) if suffix_part else None

    # Additional tokens: anything we didn't classify explicitly (for future analysis)
    # (Currently we don't dig deeply; we just keep them if we want.)
    # You can extend this later.

    return (
        given,
        middle_tokens,
        surname_prefix,
        surname,
        suffix,
        nickname,
        maiden_name,
        additional_tokens,
        notes,
        warnings,
    )


def build_name_block_from_gedcom(raw_name: str, name_children: Iterable[Dict[str, Any]]) -> Optional[NameBlock]:
    """
    Build a NameBlock from raw NAME string + child tags.

    - Uses child tags where present.
    - Falls back to parsing the raw NAME line.
    - Applies noise stripping and canonicalization for normalized.full_name_normalized.

    Returns:
        NameBlock instance or None (if raw_name is empty).
    """
    raw_name = safe_str(raw_name)
    if not raw_name.strip():
        return None

    # Parse child tags
    child_map = extract_name_children(name_children)

    # Start from raw-line parse
    (
        given,
        middle_tokens,
        surname_prefix,
        surname,
        suffix,
        nickname,
        maiden_name,
        additional_tokens,
        notes,
        warnings,
    ) = parse_raw_name_line(raw_name)

    # Override with child tags if present
    if "givn" in child_map:
        givn = normalize_whitespace(child_map["givn"])
        tokens = [t for t in givn.split(" ") if t]
        if tokens:
            given = normalize_case(tokens[0])
            middle_tokens = [normalize_case(t) for t in tokens[1:]]

    if "surn" in child_map:
        surname = normalize_case(child_map["surn"])

    if "npfx" in child_map:
        prefix = normalize_case(child_map["npfx"])
    else:
        prefix = None

    if "spfx" in child_map:
        surname_prefix = normalize_case(child_map["spfx"])

    if "nsfx" in child_map:
        suffix = normalize_case(child_map["nsfx"])

    if "nick" in child_map:
        nickname = normalize_case(child_map["nick"])

    title = None
    if "titl" in child_map:
        title = normalize_case(child_map["titl"])

    # Build canonical normalized.full and normalized.full_name_normalized
    canonical_tokens: List[str] = []

    if given:
        canonical_tokens.append(given)

    if middle_tokens:
        canonical_tokens.extend(middle_tokens)

    if surname_prefix:
        canonical_tokens.append(surname_prefix)

    if surname:
        canonical_tokens.append(surname)

    if suffix:
        canonical_tokens.append(suffix)

    canonical_joined = " ".join(t for t in canonical_tokens if t)
    canonical_joined = normalize_whitespace(canonical_joined)

    # full_name_normalized = lowercase, punctuation-stripped comparison key
    comparison = canonical_joined.lower()
    comparison = re.sub(r"[^a-z0-9]+", " ", comparison)
    comparison = re.sub(r"\s+", " ", comparison).strip()

    normalized = NormalizedName(
        given=given or None,
        middle=middle_tokens,
        nickname=nickname or None,
        surname_prefix=surname_prefix or None,
        surname=surname or None,
        suffix=suffix or None,
        title=title or None,
        maiden_name=maiden_name or None,
        full=canonical_joined,
        full_name_normalized=comparison,
        romanized=None,
        phonetic=None,
        alias=None,
    )

    parsed = ParsedName(
        prefix=prefix,
        title=title,
        given=given or None,
        middle=middle_tokens,
        nickname=nickname or None,
        surname_prefix=surname_prefix or None,
        surname=surname or None,
        suffix=suffix or None,
        maiden_name=maiden_name or None,
        additional_tokens=additional_tokens,
        notes=notes,
        warnings=warnings,
    )

    block = NameBlock(
        raw=raw_name,
        parsed=parsed,
        normalized=normalized,
    )
    return block


# ---------------------------------------------------------------------------
# Registry-level processing
# ---------------------------------------------------------------------------


def find_primary_name_and_children(indi: Dict[str, Any]) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    """
    For a given individual record (from registry["individuals"][id]):

    - Use the first entry in "names" list as the primary NAME raw string.
    - Use the first NAME node in "raw_children" as the source of child tags.

    Returns:
        (raw_name, name_children_list)
    """
    raw_name: Optional[str] = None
    name_children: List[Dict[str, Any]] = []

    # Prefer individuals["names"][0]
    names_field = indi.get("names")
    if isinstance(names_field, list) and names_field:
        for n in names_field:
            if isinstance(n, str) and n.strip():
                raw_name = n
                break

    # Also search raw_children for the first NAME tag
    for rc in indi.get("raw_children", []):
        if safe_str(rc.get("tag")).upper() == "NAME":
            if raw_name is None:
                raw_name = safe_str(rc.get("value"))
            name_children = rc.get("children", []) or []
            break

    return raw_name, name_children


def normalize_registry(registry: Dict[str, Any], debug: bool = False) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Walk registry["individuals"], build / update "name_block" for each.

    Returns:
        (updated_registry, summary_dict)
    """
    individuals = registry.get("individuals", {}) or {}
    indi_ids = list(individuals.keys())

    total_names = 0
    names_normalized = 0
    errors = 0

    for indi_id in indi_ids:
        indi = individuals.get(indi_id) or {}
        raw_name, name_children = find_primary_name_and_children(indi)

        if not raw_name:
            if debug:
                log.debug("No primary NAME found for %s; skipping.", indi_id)
            continue

        total_names += 1

        try:
            block = build_name_block_from_gedcom(raw_name, name_children)
            if block is None:
                if debug:
                    log.debug("build_name_block_from_gedcom returned None for %s", indi_id)
                continue

            indi["name_block"] = block.model_dump(mode="python")
            names_normalized += 1

        except Exception as exc:  # pragma: no cover
            errors += 1
            # If debug, log full traceback; otherwise, short error in log file.
            log.exception("Error normalizing name for %s: %s", indi_id, exc)

    summary = {
        "individuals": len(indi_ids),
        "total_names": total_names,
        "names_normalized": names_normalized,
        "errors": errors,
    }

    return registry, summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def run_cli(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        description="Normalize individual names into NameBlock structures."
    )
    parser.add_argument(
        "-i",
        "--input",
        required=True,
        help="Input registry JSON (e.g., outputs/export_xref.json)",
    )
    parser.add_argument(
        "-o",
        "--output",
        required=True,
        help="Output registry JSON with normalized name_block entries.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable verbose debug logging.",
    )

    args = parser.parse_args(argv)

    if args.debug:
        log.setLevel(logging.DEBUG)

    log.info(
        "Name normalization starting. Input=%s, Output=%s",
        args.input,
        args.output,
    )
    log.info("Loading JSON: %s", args.input)

    with open(args.input, "r", encoding="utf-8") as f:
        registry = json.load(f)

    updated, summary = normalize_registry(registry, debug=args.debug)

    log.info(
        "Name normalization summary: individuals=%d, total_names=%d, names_normalized=%d, errors=%d",
        summary.get("individuals", 0),
        summary.get("total_names", 0),
        summary.get("names_normalized", 0),
        summary.get("errors", 0),
    )

    log.info("Writing JSON: %s", args.output)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(updated, f, indent=2, ensure_ascii=False)

    log.info("Name normalization output written to: %s", args.output)
    print(f"[name_normalization] Output written to: {args.output}")


def main() -> None:
    run_cli()


if __name__ == "__main__":
    main()
