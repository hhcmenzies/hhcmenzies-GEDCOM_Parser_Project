"""
C.24.4.6 – UUID Identity Layer

Centralized, deterministic UUID generation for:
- Top-level records (INDI, FAM, SOUR, REPO, OBJE)
- Names
- Events
- Occupations

Design goals:
- Deterministic: same logical identity -> same UUID every run.
- Stable across refactors: based on semantic keys, not memory layout.
- Flexible: callers can pass either normalized dicts or simple strings
  (for names), without breaking.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any, Optional


# ==========================================================
# INTERNAL HELPER
# ==========================================================

def _hash_to_uuid(namespace: str, payload: Any) -> str:
    """
    Deterministically map (namespace, payload) -> UUID.

    We SHA-256 the JSON-encoded payload, then slice the first 32 hex
    chars into a UUID.

    This is *not* cryptographic identity; it's just a stable mapping.
    """
    key = json.dumps({"ns": namespace, "payload": payload}, sort_keys=True)
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return str(uuid.UUID(h[:32]))


# ==========================================================
# RECORD-LEVEL UUIDs
# ==========================================================

def uuid_for_record(record_type: str, pointer: Optional[str]) -> Optional[str]:
    """
    Stable UUID for any top-level GEDCOM record (INDI/FAM/SOUR/REPO/OBJE),
    keyed solely by its pointer and record_type.

    If pointer is missing, returns None (caller can decide how to handle
    anonymous / synthetic records).
    """
    if not pointer:
        return None

    payload = {
        "record_type": record_type,
        "pointer": pointer,
    }
    return _hash_to_uuid("record", payload)


def uuid_for_pointer(record_type: str, pointer: Optional[str]) -> Optional[str]:
    """
    Thin wrapper kept for caller convenience.

    Semantics: identical to uuid_for_record(record_type, pointer).
    """
    return uuid_for_record(record_type, pointer)


# ==========================================================
# NAME UUIDs
# ==========================================================

def uuid_for_name(pointer: Optional[str], name_block: Any) -> Optional[str]:
    """
    Deterministic UUID for a *logical name identity*.

    Supports two calling patterns (for backward compatibility):

    1) pointer + normalized name dict (preferred):
        name_block = {
            "prefix": ...,
            "given": ...,
            "middle": ...,
            "surname_prefix": ...,
            "surname": ...,
            "suffix": ...,
            "full": ...,
            "full_name_normalized": ...,
            ...
        }

    2) pointer + string (fallback / legacy):
        name_block = "David Thomas /Menzies/"

    In both cases, we hash a structured payload containing:
      - the owning record pointer (if present)
      - the normalized/full name info
    """
    if pointer is None and not name_block:
        return None

    # Dict-style: assume it's already a structured block
    if isinstance(name_block, dict):
        payload = {
            "ptr": pointer,
            "name": {
                "prefix": name_block.get("prefix"),
                "given": name_block.get("given"),
                "middle": name_block.get("middle"),
                "surname_prefix": name_block.get("surname_prefix"),
                "surname": name_block.get("surname"),
                "suffix": name_block.get("suffix"),
                "full": name_block.get("full"),
                "normalized": name_block.get("full_name_normalized"),
            },
        }
    else:
        # String-style: treat as a single full name field
        payload = {
            "ptr": pointer,
            "name": {
                "full": str(name_block),
            },
        }

    return _hash_to_uuid("name", payload)


# ==========================================================
# EVENT UUIDs
# ==========================================================

def uuid_for_event(
    record_uuid: Optional[str],
    tag: str,
    date: str,
    place_raw: str,
) -> Optional[str]:
    """
    Deterministic UUID for a particular event instance on a record.

    Keyed by:
      - parent record UUID
      - event tag (BIRT/DEAT/MARR/etc.)
      - raw date string
      - raw place string

    If record_uuid is missing, returns None (caller can treat such events
    as anonymous or synthetic).
    """
    if not record_uuid:
        return None

    payload = {
        "record_uuid": record_uuid,
        "tag": tag,
        "date": date,
        "place_raw": place_raw,
    }
    return _hash_to_uuid("event", payload)


# ==========================================================
# OCCUPATION UUIDs
# ==========================================================

def uuid_for_occupation(
    record_uuid: Optional[str],
    primary: str,
) -> Optional[str]:
    """
    Deterministic UUID for an occupation identity block.

    Keyed by:
      - parent record UUID (if any)
      - primary occupation string (normalized by caller)
    """
    if not record_uuid and not primary:
        return None

    payload = {
        "record_uuid": record_uuid,
        "primary": primary,
    }
    return _hash_to_uuid("occupation", payload)
