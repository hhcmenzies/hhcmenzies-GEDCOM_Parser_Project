"""
name_block.py
Canonical structured representation of GEDCOM names (dependency-free).

Defines:
- ParsedName:      Low-level tokens extracted from raw NAME + child tags
- NormalizedName:  Cleaned, case-normalized, noise-filtered canonical view
- NameBlock:       Full container stored into export JSON

Design requirements (preserved from prior longer module):
- Middle names = list[str]
- Parentheses may indicate nickname or maiden name
- Quoted fragments treated as nickname candidates
- Noise (emoji, symbols, stray punctuation) removed in normalized view
- Must support UUID for reproducibility
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import re
import uuid


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

_WS_RE = re.compile(r"\s+")
# Keep letters/numbers/space plus a small set of safe separators.
# (We strip everything else in normalized view.)
_NOISE_RE = re.compile(r"[^0-9A-Za-z\s\-\.'’]")

# Capture quoted fragments: "Bob" or 'Bob'
_QUOTED_RE = re.compile(r"""(["'])(.+?)\1""")

# Parentheses: (something)
_PARENS_RE = re.compile(r"\(([^)]+)\)")

# GEDCOM surname markers: Given /Surname/ Suffix
_SURNAME_MARKED_RE = re.compile(r"(.*?)/([^/]+)/\s*(.*)$")


def _clean_ws(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    out = _WS_RE.sub(" ", str(s)).strip()
    return out or None


def _strip_noise_for_normalized(s: str) -> str:
    # Normalize whitespace and remove noisy symbols (emoji, etc.)
    s2 = _clean_ws(s) or ""
    s2 = _NOISE_RE.sub("", s2)
    s2 = _WS_RE.sub(" ", s2).strip()
    return s2


def _title_case_loose(s: str) -> str:
    # Conservative: keep internal punctuation, title-case token-wise.
    parts = []
    for tok in (_clean_ws(s) or "").split(" "):
        if not tok:
            continue
        if tok.isupper():
            # Likely acronym; keep.
            parts.append(tok)
        else:
            parts.append(tok[:1].upper() + tok[1:].lower() if tok else tok)
    return " ".join(parts).strip()


def _lower_canonical(s: str) -> str:
    # Canonical comparison string.
    return (_strip_noise_for_normalized(s)).lower()


def _split_middle(given: Optional[str]) -> tuple[Optional[str], List[str]]:
    """
    If `given` contains multiple tokens, treat the first as given and
    remainder as middle.
    """
    g = _clean_ws(given)
    if not g:
        return None, []
    toks = g.split(" ")
    if len(toks) == 1:
        return g, []
    return toks[0], toks[1:]


def _extract_quoted_nickname(raw: str) -> Optional[str]:
    m = _QUOTED_RE.search(raw)
    if not m:
        return None
    return _clean_ws(m.group(2))


def _extract_parens_token(raw: str) -> Optional[str]:
    m = _PARENS_RE.search(raw)
    if not m:
        return None
    return _clean_ws(m.group(1))


def _remove_quotes_and_parens(raw: str) -> str:
    # Remove quoted fragments and parenthetical fragments for base token parsing
    raw2 = _QUOTED_RE.sub("", raw)
    raw2 = _PARENS_RE.sub("", raw2)
    return _clean_ws(raw2) or ""


# -----------------------------------------------------------------------------
# Data models (dependency-free; pydantic-compatible API surface where helpful)
# -----------------------------------------------------------------------------

@dataclass(slots=True)
class ParsedName:
    prefix: Optional[str] = None          # e.g., "Dr.", "Sir"
    title: Optional[str] = None           # e.g., "PhD"
    given: Optional[str] = None
    middle: List[str] = field(default_factory=list)
    nickname: Optional[str] = None
    surname_prefix: Optional[str] = None  # e.g., "van", "de", "Mac"
    surname: Optional[str] = None
    suffix: Optional[str] = None          # e.g., "Jr.", "III"

    maiden_name: Optional[str] = None     # from "( )" or child tags

    additional_tokens: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prefix": self.prefix,
            "title": self.title,
            "given": self.given,
            "middle": list(self.middle),
            "nickname": self.nickname,
            "surname_prefix": self.surname_prefix,
            "surname": self.surname,
            "suffix": self.suffix,
            "maiden_name": self.maiden_name,
            "additional_tokens": list(self.additional_tokens),
            "notes": list(self.notes),
            "warnings": list(self.warnings),
        }


@dataclass(slots=True)
class NormalizedName:
    given: Optional[str] = None
    middle: List[str] = field(default_factory=list)
    nickname: Optional[str] = None
    surname_prefix: Optional[str] = None
    surname: Optional[str] = None
    suffix: Optional[str] = None
    title: Optional[str] = None
    maiden_name: Optional[str] = None

    full: str = ""                 # e.g., "david thomas menzies"
    full_name_normalized: str = "" # canonical comparison string

    romanized: Optional[str] = None
    phonetic: Optional[str] = None
    alias: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "given": self.given,
            "middle": list(self.middle),
            "nickname": self.nickname,
            "surname_prefix": self.surname_prefix,
            "surname": self.surname,
            "suffix": self.suffix,
            "title": self.title,
            "maiden_name": self.maiden_name,
            "full": self.full,
            "full_name_normalized": self.full_name_normalized,
            "romanized": self.romanized,
            "phonetic": self.phonetic,
            "alias": self.alias,
        }


@dataclass(slots=True)
class NameBlock:
    raw: str = ""  # raw NAME line, e.g., "David Thomas /Menzies/"
    uuid: str = field(default_factory=lambda: str(uuid.uuid4()))

    parsed: ParsedName = field(default_factory=ParsedName)
    normalized: NormalizedName = field(default_factory=NormalizedName)

    # Compatibility helpers (similar ergonomics to pydantic)
    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw": self.raw,
            "uuid": self.uuid,
            "parsed": self.parsed.to_dict(),
            "normalized": self.normalized.to_dict(),
        }

    # Alias used by many codebases migrating off pydantic
    def model_dump(self) -> Dict[str, Any]:
        return self.to_dict()


# -----------------------------------------------------------------------------
# Parsing / normalization engine
# -----------------------------------------------------------------------------

def parse_name_block(
    *,
    raw_full: str,
    given: Optional[str] = None,
    surname: Optional[str] = None,
    prefix: Optional[str] = None,
    suffix: Optional[str] = None,
    nickname: Optional[str] = None,
    name_type: Optional[str] = None,
    raw_meta: Optional[Dict[str, Any]] = None,
) -> NameBlock:
    """
    Build a NameBlock from the modern export fields (full/given/surname/etc)
    plus GEDCOM raw NAME string.

    Never raises; always returns a NameBlock.
    """
    raw_full_clean = _clean_ws(raw_full) or ""
    nb = NameBlock(raw=raw_full_clean)

    pn = ParsedName()
    nn = NormalizedName()

    # 1) Derive from GEDCOM marked surname if present
    base = raw_full_clean
    m = _SURNAME_MARKED_RE.match(base)
    if m:
        pre = _clean_ws(m.group(1))
        sur = _clean_ws(m.group(2))
        post = _clean_ws(m.group(3))
        pn.given = pre
        pn.surname = sur
        pn.suffix = post
    else:
        # If no /Surname/ markers, treat whole string as given-ish base
        pn.given = _clean_ws(base) or None

    # 2) Overlay explicit structured fields (authoritative if provided)
    pn.prefix = _clean_ws(prefix)
    pn.title = _clean_ws(name_type)  # "TYPE" in GEDCOM often behaves like name type/title
    pn.suffix = _clean_ws(suffix) or pn.suffix

    # 3) Nickname candidates: quoted fragments or explicit nickname field
    qnick = _extract_quoted_nickname(base)
    pn.nickname = _clean_ws(nickname) or qnick

    # 4) Parentheses candidate: treat as maiden_name if it looks like surname-ish,
    # otherwise as nickname fallback (conservative).
    par = _extract_parens_token(base)
    if par:
        # Heuristic: multi-token or starts with uppercase -> likely surname/maiden; keep as maiden_name
        pn.maiden_name = par

    # 5) If explicit given/surname provided, use them; else keep parsed
    pn.given = _clean_ws(given) or pn.given
    pn.surname = _clean_ws(surname) or pn.surname

    # 6) Middle names: split from given if it contains multiple tokens
    g_first, g_middle = _split_middle(pn.given)
    pn.given = g_first
    pn.middle = g_middle

    # 7) Extract additional tokens from the raw string (noise removed)
    core = _remove_quotes_and_parens(base)
    core = core.replace("/", " ")
    toks = [t for t in (_clean_ws(core) or "").split(" ") if t]
    # Don't re-add tokens we already modeled
    modeled = set()
    for t in [pn.prefix, pn.title, pn.given, pn.nickname, pn.surname_prefix, pn.surname, pn.suffix, pn.maiden_name]:
        if t:
            modeled.update((_clean_ws(t) or "").split(" "))
    for t in pn.middle:
        modeled.add(t)
    extras = [t for t in toks if t not in modeled]
    pn.additional_tokens = extras

    # 8) Build normalized view
    nn.given = _title_case_loose(pn.given) if pn.given else None
    nn.middle = [_title_case_loose(m) for m in pn.middle]
    nn.nickname = _title_case_loose(pn.nickname) if pn.nickname else None
    nn.surname_prefix = _title_case_loose(pn.surname_prefix) if pn.surname_prefix else None
    nn.surname = _title_case_loose(pn.surname) if pn.surname else None
    nn.suffix = _title_case_loose(pn.suffix) if pn.suffix else None
    nn.title = _title_case_loose(pn.title) if pn.title else None
    nn.maiden_name = _title_case_loose(pn.maiden_name) if pn.maiden_name else None

    # Full normalized composite (noise stripped, lower canonical)
    parts: List[str] = []
    for p in [nn.given, *nn.middle, nn.surname_prefix, nn.surname, nn.suffix]:
        if p:
            parts.append(p)
    full_pretty = " ".join(parts).strip()
    nn.full = _lower_canonical(full_pretty)
    nn.full_name_normalized = nn.full  # reserved for future stronger canonicalization

    # 9) Metadata / notes / warnings
    if raw_meta:
        pn.notes.append("raw_meta_present")
        # No mutation of raw_meta here; caller stores it.

    if not pn.surname and "/" in raw_full_clean:
        pn.warnings.append("surname_markers_present_but_surname_missing")

    nb.parsed = pn
    nb.normalized = nn
    return nb
