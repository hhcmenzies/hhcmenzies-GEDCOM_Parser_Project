"""
gedcom_parser.entities package

This package defines the core entity layer for the GEDCOM parser, including:

- BaseEntity: common base class for entity types.
- (Elsewhere) concrete entity models and registry helpers.

To avoid circular imports, this __init__ keeps exports minimal.
"""

from __future__ import annotations

from .entity_base import BaseEntity

__all__ = ["BaseEntity"]
