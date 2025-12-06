"""
gedcom_parser.entities package

Phase 1 — minimal, safe exports.

We intentionally DO NOT import registry or models here yet because
Phase 1 is building the new backbone and those modules are not complete.

Only export BaseEntity for now.
"""

from .entity_base import BaseEntity

__all__ = [
    "BaseEntity",
]
