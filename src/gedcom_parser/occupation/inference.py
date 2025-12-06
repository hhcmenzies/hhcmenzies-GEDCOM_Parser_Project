import json
import os
import re
from typing import Any, Dict, List, Tuple

_OCCUPATION_MAP_CACHE: Dict[str, List[str]] | None = None


def load_occupation_map() -> Dict[str, List[str]]:
    """
    Load the occupation keyword map from data/occupation_keywords.json.
    Uses a simple in-memory cache so it only hits disk once.
    """
    global _OCCUPATION_MAP_CACHE
    if _OCCUPATION_MAP_CACHE is not None:
        return _OCCUPATION_MAP_CACHE

    base_dir = os.path.dirname(os.path.dirname(__file__))
    data_path = os.path.join(base_dir, "data", "occupation_keywords.json")

    if not os.path.exists(data_path):
        raise FileNotFoundError(f"Occupation keyword map not found: {data_path}")

    with open(data_path, "r", encoding="utf-8") as f:
        _OCCUPATION_MAP_CACHE = json.load(f)

    return _OCCUPATION_MAP_CACHE


def _normalize_text(text: str) -> str:
    """
    Lowercase and strip to alphanumeric plus spaces.
    Good enough for simple substring matching.
    """
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return text.strip()


def _find_occupations_in_text(
    text: str,
    occ_map: Dict[str, List[str]],
) -> List[Tuple[str, str]]:
    """
    Given some free text and the occupation map, return a list of
    (canonical, matched_variant) pairs that appear in that text.
    """
    results: List[Tuple[str, str]] = []
    if not text:
        return results

    norm_text = _normalize_text(text)
    if not norm_text:
        return results

    for canonical, variants in occ_map.items():
        for variant in variants:
            vnorm = _normalize_text(variant)
            if not vnorm:
                continue
            if vnorm in norm_text:
                results.append((canonical, variant))
                break  # only need one variant hit per canonical

    return results


def infer_occupations(
    explicit_occus: List[str],
    note_texts: List[str],
) -> Dict[str, Any]:
    """
    Given OCCU field values and NOTE text, infer normalized occupations.

    Returns a struct:
        {
          "explicit": [...],            # from OCCU
          "inferred_from_notes": [...], # from NOTE content
          "all": [...],                 # union, sorted
          "raw_terms": {
            "OCCU": [...],
            "NOTE": [...],
          },
        }
    """
    occ_map = load_occupation_map()

    explicit_hits: List[str] = []
    inferred_hits: List[str] = []

    # OCCU-based
    for val in explicit_occus:
        for canonical, variant in _find_occupations_in_text(val, occ_map):
            explicit_hits.append(canonical)

    # NOTE-based
    for val in note_texts:
        for canonical, variant in _find_occupations_in_text(val, occ_map):
            inferred_hits.append(canonical)

    explicit_set = sorted(set(explicit_hits))
    inferred_set = sorted(set(inferred_hits))
    all_set = sorted(set(explicit_hits + inferred_hits))

    return {
        "explicit": explicit_set,
        "inferred_from_notes": inferred_set,
        "all": all_set,
        "raw_terms": {
            "OCCU": list(explicit_occus),
            "NOTE": list(note_texts),
        },
    }
