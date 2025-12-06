"""
Place / Location extraction utilities.

Supports:
- PLAC text parsing
- MAP → LATI / LONG extraction
- N/S/E/W → +/- decimal conversion
- Highly inconsistent GEDCOM formatting
"""

from typing import Dict, Any, List, Optional
import re


# =====================================================================
# Coordinate parsing helpers
# =====================================================================

def _normalize_coordinate(value: str) -> Optional[float]:
    """
    Convert GEDCOM coordinate formats to signed float.

    Accepts:
      LATI N43.123
      LATI S12.50
      LONG W70.12
      LONG E10.945

    Returns:
      float (signed) or None
    """

    if not value:
        return None

    v = value.strip().upper()

    # Extract direction letter
    m = re.match(r"([NSWE])\s*([0-9.+-]+)", v)
    if m:
        direction = m.group(1)
        number = float(m.group(2))

        if direction == "S":
            return -abs(number)
        if direction == "N":
            return abs(number)
        if direction == "W":
            return -abs(number)
        if direction == "E":
            return abs(number)

    # fallback: raw float
    try:
        return float(v)
    except ValueError:
        return None


# =====================================================================
# PLAC text parsing
# =====================================================================

def _parse_place_string(raw: str) -> Dict[str, Any]:
    """
    Split a PLAC string into hierarchical components.

    GEDCOM commonly uses:
      City, County, State, Country

    We support partial forms as well.
    """

    if not raw:
        return {
            "raw": None,
            "parts": {},
        }

    parts = [p.strip() for p in raw.split(",") if p.strip()]

    mapping = {}
    if len(parts) >= 1:
        mapping["city"] = parts[0]
    if len(parts) >= 2:
        mapping["county"] = parts[1]
    if len(parts) >= 3:
        mapping["state"] = parts[2]
    if len(parts) >= 4:
        mapping["country"] = parts[3]

    return {
        "raw": raw,
        "parts": mapping,
    }


# =====================================================================
# MAIN ENTRY
# =====================================================================

def extract_place_block(event_node: Dict[str, Any]) -> Dict[str, Any]:
    """
    Given a BIRT/DEAT/MARR/etc node, extract:
      - PLAC (string)
      - MAP/LATI/LONG (coords)

    Returns:
    {
      "raw": str or None,
      "parts": {...},
      "coordinates": {
          "lat": float or None,
          "lon": float or None
      }
    }
    """

    plac_value = None
    lat = None
    lon = None

    # First pass: get PLAC
    for child in event_node.get("children", []):
        if child["tag"] == "PLAC":
            plac_value = child["value"]

    # Second pass: look for MAP children
    for child in event_node.get("children", []):
        if child["tag"] == "MAP":
            for sub in child.get("children", []):
                if sub["tag"] == "LATI":
                    lat = _normalize_coordinate(sub["value"])
                elif sub["tag"] == "LONG":
                    lon = _normalize_coordinate(sub["value"])

    base = _parse_place_string(plac_value)

    return {
        "raw": plac_value,
        "parts": base["parts"],
        "coordinates": {
            "lat": lat,
            "lon": lon,
        }
    }
