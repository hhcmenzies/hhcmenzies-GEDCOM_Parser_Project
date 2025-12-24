# src/gedcom_parser/identity/uuid_factory.py
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Optional


# -----------------------------
# Core deterministic hashing
# -----------------------------

def _stable_hash(key: str) -> str:
    # Deterministic stable hashing; SHA1 is fine for identity/fingerprints (not security).
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


def _uuid_from_key(key: str) -> str:
    """
    Convert an arbitrary key string into a canonical UUID-like value (8-4-4-4-12)
    based on SHA1. Deterministic for the same key.
    """
    h = _stable_hash(key)
    h32 = h[:32]
    return f"{h32[0:8]}-{h32[8:12]}-{h32[12:16]}-{h32[16:20]}-{h32[20:32]}"


def deterministic_uuid(*parts: object) -> str:
    """
    Backwards-compatible helper used across the codebase.
    """
    key = "|".join("" if p is None else str(p) for p in parts)
    return _uuid_from_key(key)


# -----------------------------
# Pointer normalization
# -----------------------------

def normalize_pointer(pointer: Optional[str]) -> Optional[str]:
    """
    Normalize GEDCOM pointer:
      - strip whitespace
      - uppercase
      - ensure wrapped in @...@
    """
    if pointer is None:
        return None

    p = pointer.strip().upper()
    if not p:
        return None

    if not (p.startswith("@") and p.endswith("@")):
        # best-effort normalization
        if "@" not in p:
            p = f"@{p}@"
        else:
            if not p.startswith("@"):
                p = "@" + p
            if not p.endswith("@"):
                p = p + "@"

    return p


def uuid_for_pointer(pointer: str) -> str:
    p = normalize_pointer(pointer)
    if p is None:
        raise ValueError(f"Invalid pointer: {pointer!r}")
    return _uuid_from_key(f"PTR|{p}")


# -----------------------------
# Record identity (non-pointer)
# -----------------------------

def uuid_for_record(record_node: Dict[str, Any]) -> str:
    """
    Deterministic UUID for a record dict (used for promotion/fingerprints).
    We intentionally include structure so two different inline OBJE nodes
    don't collide.
    """
    tag = (record_node.get("tag") or "UNK").upper()
    value = record_node.get("value")
    lineno = record_node.get("lineno")
    pointer = record_node.get("pointer")

    children = record_node.get("children") or []
    child_fps = []
    for c in children:
        ctag = (c.get("tag") or "UNK").upper()
        cval = c.get("value")
        child_fps.append(f"{ctag}:{'' if cval is None else str(cval)}")

    payload = {
        "tag": tag,
        "value": value,
        "lineno": lineno,
        "pointer": pointer,
        "children": child_fps,
    }

    key = "REC|" + json.dumps(payload, sort_keys=True, default=str)
    return _uuid_from_key(key)


# -----------------------------
# Sub-identities used by tests
# -----------------------------

def uuid_for_name(record_uuid: str, full_name: str) -> str:
    """
    Deterministic identity for a NameRecord attached to an entity.
    """
    return _uuid_from_key(f"NAME|{record_uuid}|{(full_name or '').strip()}")


def uuid_for_event(
    record_uuid: str,
    tag: str,
    date: str = "",
    place: str = "",
) -> str:
    """
    Deterministic identity for an event attached to an entity.
    """
    t = (tag or "").strip().upper()
    d = (date or "").strip()
    p = (place or "").strip()
    return _uuid_from_key(f"EVT|{record_uuid}|{t}|{d}|{p}")


def uuid_for_occupation(record_uuid: str, occ: Any) -> str:
    """
    Deterministic occupation identity.
    Tests may pass either a string or a dict.
    """
    if isinstance(occ, str):
        payload = occ.strip()
    elif isinstance(occ, dict):
        payload = json.dumps(occ, sort_keys=True, default=str)
    else:
        payload = str(occ)
    return _uuid_from_key(f"OCCU|{record_uuid}|{payload}")


def uuid_for_inline_media(
    *,
    owner_uuid: Optional[str],
    owner_pointer: Optional[str],
    lineno: Optional[int],
    file: Optional[str],
    title: Optional[str],
) -> str:
    """
    Deterministic identity for promoted inline OBJE media objects.
    """
    payload = {
        "owner_uuid": owner_uuid,
        "owner_pointer": owner_pointer,
        "lineno": lineno,
        "file": file,
        "title": title,
    }
    key = "IMEDIA|" + json.dumps(payload, sort_keys=True, default=str)
    return _uuid_from_key(key)


__all__ = [
    "deterministic_uuid",
    "normalize_pointer",
    "uuid_for_pointer",
    "uuid_for_record",
    "uuid_for_name",
    "uuid_for_event",
    "uuid_for_occupation",
    "uuid_for_inline_media",
]
