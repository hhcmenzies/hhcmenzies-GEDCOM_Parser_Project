"""
name_block.py
Canonical structured representation of GEDCOM names.

This module defines:
- ParsedName:    Low-level tokens extracted from the raw NAME line + child tags
- NormalizedName: Cleaned, case-normalized, noise-filtered canonical name
- NameBlock:      The full container stored in registry JSON

Design requirements:
- Middle names = list[str]
- Parentheses may indicate nickname or maiden name
- Quoted fragments should be treated as nickname candidates
- Noise (emoji, symbols, stray punctuation) removed in normalized view
- Must support UUID for reproducibility
"""

from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, Field
import uuid


# -------------------------------------------------------------
# Low-level parsed representation (closest to the GEDCOM input)
# -------------------------------------------------------------
class ParsedName(BaseModel):
    prefix: Optional[str] = None          # e.g., "Dr.", "Sir"
    title: Optional[str] = None           # e.g., "PhD"
    given: Optional[str] = None
    middle: List[str] = Field(default_factory=list)
    nickname: Optional[str] = None
    surname_prefix: Optional[str] = None  # e.g., "van", "de", "Mac"
    surname: Optional[str] = None
    suffix: Optional[str] = None          # e.g., "Jr.", "III"

    maiden_name: Optional[str] = None     # from "( )" or child tags

    additional_tokens: List[str] = Field(default_factory=list)
    # tokens we didn’t classify (yet)

    notes: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


# -------------------------------------------------------------
# Canonical normalized representation
# -------------------------------------------------------------
class NormalizedName(BaseModel):
    given: Optional[str] = None
    middle: List[str] = Field(default_factory=list)
    nickname: Optional[str] = None
    surname_prefix: Optional[str] = None
    surname: Optional[str] = None
    suffix: Optional[str] = None
    title: Optional[str] = None
    maiden_name: Optional[str] = None

    # Fully normalized output (no noise; standardized case)
    full: str = ""                       # normalized composite, e.g., "david thomas menzies"
    full_name_normalized: str = ""       # canonical comparison string

    # Reserved for future features
    romanized: Optional[str] = None
    phonetic: Optional[str] = None
    alias: Optional[str] = None


# -------------------------------------------------------------
# Full block stored in registry JSON
# -------------------------------------------------------------
class NameBlock(BaseModel):
    raw: str = ""                                # raw NAME line (e.g., "David Thomas /Menzies/")
    uuid: str = Field(default_factory=lambda: str(uuid.uuid4()))

    parsed: ParsedName
    normalized: NormalizedName

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
