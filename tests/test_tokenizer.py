# tests/test_tokenizer.py

from __future__ import annotations

from pathlib import Path

import pytest

from gedcom_parser.loader import GedcomSyntaxError, tokenize_line, tokenize_file
from gedcom_parser.utils import mock_file_path


def test_tokenize_line_simple_head() -> None:
    token = tokenize_line("0 HEAD", lineno=1)
    assert token.lineno == 1
    assert token.level == 0
    assert token.pointer is None
    assert token.tag == "HEAD"
    assert token.value == ""


def test_tokenize_line_with_pointer_and_tag_only() -> None:
    token = tokenize_line("0 @I1@ INDI", lineno=1)
    assert token.level == 0
    assert token.pointer == "@I1@"
    assert token.tag == "INDI"
    assert token.value == ""


def test_tokenize_line_with_value() -> None:
    line = "1 NOTE This is a test note"
    token = tokenize_line(line, lineno=10)
    assert token.level == 1
    assert token.pointer is None
    assert token.tag == "NOTE"
    assert token.value == "This is a test note"
    assert token.raw == line


def test_tokenize_line_with_bom_on_first_line() -> None:
    # Simulate a UTF-8 BOM at the start of the first line.
    line = "\ufeff0 HEAD"
    token = tokenize_line(line, lineno=1)
    assert token.level == 0
    assert token.tag == "HEAD"
    assert token.pointer is None


def test_tokenize_line_invalid_level_raises() -> None:
    with pytest.raises(GedcomSyntaxError):
        tokenize_line("X HEAD", lineno=1)


def test_tokenize_line_missing_tag_raises() -> None:
    with pytest.raises(GedcomSyntaxError):
        tokenize_line("0 ", lineno=1)


def test_tokenize_file_reads_existing_mock_file() -> None:
    path = mock_file_path("gedcom_1.ged")
    tokens = list(tokenize_file(path))

    assert tokens, "Expected at least one token from mock GEDCOM file"
    # First line should be level 0 (usually HEAD).
    assert tokens[0].level == 0
