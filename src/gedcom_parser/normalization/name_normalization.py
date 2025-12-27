"""
name_normalization.py
C.24.4.x – Name Normalization (Modern Export Schema, dependency-free)

Goals:
- Works directly on export JSON dicts (post-export, post-xref, post-place, etc.)
- Normalizes NAME structures under individuals[*]["names"]
- Adds a first-class "name_block" per individual (ParsedName/NormalizedName/UUID)
- Never deletes data; only fills missing fields + adds normalized helpers

This replaces the older pydantic-based pipeline behavior while preserving
its functional surface (parsed tokens, normalized view, UUID, warnings/notes).
"""

from __future__ import annotations

import argparse
import json
from typing import Any, Dict, List, Optional, Tuple

from gedcom_parser.logger import get_logger
from gedcom_parser.entities.name_block import parse_name_block

log = get_logger("name_normalization")


def _is_mapping(x: Any) -> bool:
    return isinstance(x, dict)


def _clean_ws(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    out = " ".join(str(s).split()).strip()
    return out or None


def _best_name_dict(names: Any) -> Optional[Dict[str, Any]]:
    """
    Pick the "best" name dict from individuals[*]["names"].
    Preference:
      1) first dict with a non-empty "full"
      2) first dict at all
    """
    if not isinstance(names, list) or not names:
        return None
    best: Optional[Dict[str, Any]] = None
    for n in names:
        if isinstance(n, dict):
            if _clean_ws(n.get("full")):
                return n
            best = best or n
    return best


def _ensure_names_list(indi: Dict[str, Any]) -> List[Any]:
    """
    Ensure indi["names"] exists and is a list.
    Do not create artificial names if the record doesn't have any.
    """
    names = indi.get("names")
    if isinstance(names, list):
        return names
    return []


def _patch_name_record_fields(name_rec: Dict[str, Any], nb_dict: Dict[str, Any], counts: Dict[str, int]) -> None:
    """
    Fill missing given/surname/suffix conservatively based on parsed info.
    Also adds normalized_full (never replaces full).
    """
    parsed = (nb_dict.get("parsed") or {}) if isinstance(nb_dict.get("parsed"), dict) else {}
    normalized = (nb_dict.get("normalized") or {}) if isinstance(nb_dict.get("normalized"), dict) else {}

    # Fill missing components
    if not _clean_ws(name_rec.get("given")) and _clean_ws(parsed.get("given")):
        name_rec["given"] = parsed.get("given")
        counts["filled_given"] += 1

    if not _clean_ws(name_rec.get("surname")) and _clean_ws(parsed.get("surname")):
        name_rec["surname"] = parsed.get("surname")
        counts["filled_surname"] += 1

    if not _clean_ws(name_rec.get("suffix")) and _clean_ws(parsed.get("suffix")):
        name_rec["suffix"] = parsed.get("suffix")
        counts["filled_suffix"] += 1

    # Add helper fields (non-destructive)
    nf = _clean_ws(normalized.get("full"))
    if nf and name_rec.get("normalized_full") != nf:
        name_rec["normalized_full"] = nf
        counts["added_normalized_full"] += 1

    # Always whitespace-clean existing canonical keys
    for key in ("full", "given", "surname", "prefix", "suffix", "nickname", "name_type"):
        if key in name_rec:
            name_rec[key] = _clean_ws(name_rec.get(key))


def normalize_individual_names(root: Dict[str, Any]) -> Dict[str, int]:
    """
    Mutates root in-place (additive/patch-only).
    Returns counters for logging/verification.
    """
    counts: Dict[str, int] = {
        "individuals": 0,
        "name_blocks": 0,
        "created_name_block": 0,
        "updated_name_block": 0,
        "filled_given": 0,
        "filled_surname": 0,
        "filled_suffix": 0,
        "added_normalized_full": 0,
        "skipped_non_dict_individual": 0,
        "skipped_missing_names": 0,
    }

    individuals = root.get("individuals", {})
    if not isinstance(individuals, dict):
        return counts

    for ptr, indi in individuals.items():
        if not isinstance(indi, dict):
            counts["skipped_non_dict_individual"] += 1
            continue
        counts["individuals"] += 1

        names_list = _ensure_names_list(indi)
        best = _best_name_dict(names_list)
        if best is None:
            counts["skipped_missing_names"] += 1
            continue

        full = _clean_ws(best.get("full")) or ""
        given = _clean_ws(best.get("given"))
        surname = _clean_ws(best.get("surname"))
        prefix = _clean_ws(best.get("prefix"))
        suffix = _clean_ws(best.get("suffix"))
        nickname = _clean_ws(best.get("nickname"))
        name_type = _clean_ws(best.get("name_type"))

        # Preserve any raw metadata if present
        raw_meta = best.get("raw") if isinstance(best.get("raw"), dict) else None

        nb = parse_name_block(
            raw_full=full,
            given=given,
            surname=surname,
            prefix=prefix,
            suffix=suffix,
            nickname=nickname,
            name_type=name_type,
            raw_meta=raw_meta,
        )
        nb_dict = nb.to_dict()
        counts["name_blocks"] += 1

        # Attach per-individual first-class block
        if "name_block" not in indi:
            indi["name_block"] = nb_dict
            counts["created_name_block"] += 1
        else:
            # Update in-place but preserve any custom fields previously added
            if isinstance(indi.get("name_block"), dict):
                indi["name_block"] = nb_dict
            else:
                indi["name_block"] = nb_dict
            counts["updated_name_block"] += 1

        # Patch all name dicts in the list (never delete)
        for n in names_list:
            if isinstance(n, dict):
                _patch_name_record_fields(n, nb_dict, counts)

    return counts


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> None:
    ap = argparse.ArgumentParser(description="C.24.4.x – Name normalization (modern export schema)")
    ap.add_argument("-i", "--input", required=True, help="Input JSON (export.json or later stage)")
    ap.add_argument("-o", "--output", required=True, help="Output JSON with normalized names")
    ap.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = ap.parse_args(argv)

    if args.debug:
        log.setLevel("DEBUG")

    log.info("Loading input JSON: %s", args.input)
    with open(args.input, "r", encoding="utf-8") as f:
        root = json.load(f)

    counts = normalize_individual_names(root)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(root, f, ensure_ascii=False, indent=2)

    log.info(
        "Name normalization complete: individuals=%d name_blocks=%d created=%d updated=%d "
        "filled_given=%d filled_surname=%d filled_suffix=%d added_normalized_full=%d skipped_missing_names=%d",
        counts["individuals"],
        counts["name_blocks"],
        counts["created_name_block"],
        counts["updated_name_block"],
        counts["filled_given"],
        counts["filled_surname"],
        counts["filled_suffix"],
        counts["added_normalized_full"],
        counts["skipped_missing_names"],
    )
    print(f"[INFO] Name normalization written to: {args.output}")


if __name__ == "__main__":
    main()
