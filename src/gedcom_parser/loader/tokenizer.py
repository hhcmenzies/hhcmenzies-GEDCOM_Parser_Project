# src/gedcom_parser/loader/tokenizer.py

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional, Union


@dataclass(frozen=True)
class Token:
    """
    A single GEDCOM line token.

    Attributes:
        lineno: 1-based line number in the original file.
        level: Parsed GEDCOM level (0, 1, 2, ...).
        pointer: Optional cross-reference identifier, e.g. "@I1@" or None.
        tag: GEDCOM tag, e.g. "INDI", "FAM", "HEAD", "NOTE", "CONC", "CONT".
        value: The raw line value (payload) as a string (may be empty).
        raw: The original line content without trailing newline characters.
    """
    lineno: int
    level: int
    pointer: Optional[str]
    tag: str
    value: str
    raw: str


class GedcomSyntaxError(ValueError):
    """Raised when a GEDCOM line cannot be parsed according to basic syntax."""


def _strip_eol(line: str) -> str:
    """Strip trailing CR/LF characters but preserve all other whitespace."""
    return line.rstrip("\r\n")


def tokenize_line(line: str, lineno: int = 0) -> Token:
    """
    Parse a single GEDCOM line into a Token.

    Hybrid parsing strategy:
        - Manually split off the level.
        - Then manually detect an optional pointer (starts with '@' and
          continues until the next space).
        - Remaining part is split into TAG and optional VALUE.

    This is deliberately strict about the required order:
        <level> [<pointer>] <tag> [<value>]

    Examples:
        "0 HEAD"
        "0 @I1@ INDI"
        "1 NAME John /Doe/"
        "1 NOTE This is a note"
    """
    raw = _strip_eol(line)

    # Skip completely empty lines (they are non-standard but appear in the wild).
    if not raw.strip():
        raise GedcomSyntaxError(f"Empty or whitespace-only line at {lineno}")

    # Handle optional UTF-8 BOM on the very first line.
    if lineno == 1 and raw.startswith("\ufeff"):
        raw = raw.lstrip("\ufeff")

    # --- 1. Extract level -------------------------------------------------
    # Level is the first whitespace-delimited token and must be digits.
    # We don't use regex so we can keep this simple and debuggable.
    parts = raw.split(" ", 1)
    if len(parts) == 1:
        raise GedcomSyntaxError(
            f"Line {lineno}: missing tag (only level found) -> {raw!r}"
        )

    level_str, rest = parts[0], parts[1]
    if not level_str.isdigit():
        raise GedcomSyntaxError(
            f"Line {lineno}: level is not numeric -> {level_str!r} in {raw!r}"
        )

    level = int(level_str)
    rest = rest.lstrip(" ")

    if not rest:
        # A line must have at least a tag after the level (and optional pointer).
        raise GedcomSyntaxError(
            f"Line {lineno}: missing tag after level -> {raw!r}"
        )

    # --- 2. Extract optional pointer -------------------------------------
    pointer: Optional[str] = None

    if rest.startswith("@"):
        # Pointer must run until the next space.
        # e.g. "@I1@ INDI" -> pointer="@I1@", rest_after_ptr="INDI..."
        try:
            space_index = rest.index(" ")
        except ValueError:
            # Something like "0 @I1@" with no tag is invalid.
            raise GedcomSyntaxError(
                f"Line {lineno}: pointer present but no tag -> {raw!r}"
            ) from None

        pointer = rest[:space_index]
        rest = rest[space_index + 1 :].lstrip(" ")

        if not rest:
            raise GedcomSyntaxError(
                f"Line {lineno}: pointer present but missing tag -> {raw!r}"
            )

    # --- 3. Extract tag and optional value --------------------------------
    # Now `rest` must start with TAG, optionally followed by VALUE.
    if " " in rest:
        tag, value = rest.split(" ", 1)
        value = value  # as-is, including leading/trailing spaces
    else:
        tag, value = rest, ""

    if not tag:
        raise GedcomSyntaxError(
            f"Line {lineno}: empty tag after level/pointer -> {raw!r}"
        )

    # NOTE: We do not enforce tag character set here; we rely on later
    #       validation against known tags / regex if desired.

    return Token(
        lineno=lineno,
        level=level,
        pointer=pointer,
        tag=tag,
        value=value,
        raw=raw,
    )


def tokenize_file(path: Union[str, Path]) -> Iterator[Token]:
    """
    Yield Token objects for every non-empty GEDCOM line in the given file.

    This is a thin wrapper around tokenize_line() which adds line numbers.

    Args:
        path: Path to the GEDCOM file.

    Yields:
        Token instances, one per input line.

    Raises:
        FileNotFoundError: if `path` does not exist.
        GedcomSyntaxError: if a line is syntactically invalid.
    """
    file_path = Path(path)

    if not file_path.is_file():
        raise FileNotFoundError(f"GEDCOM file not found: {file_path}")

    with file_path.open("r", encoding="utf-8", errors="replace") as f:
        for lineno, raw_line in enumerate(f, start=1):
            stripped = _strip_eol(raw_line)

            if not stripped.strip():
                # Skip truly blank lines; they are not meaningful in GEDCOM.
                continue

            yield tokenize_line(stripped, lineno=lineno)
