# tests/test_segmenter.py

from __future__ import annotations

from pathlib import Path

from gedcom_parser.loader import tokenize_file, segment_records
from gedcom_parser.utils import mock_file_path


def test_mock_file_exists() -> None:
    """
    Ensure the mock GEDCOM file is accessible and our path resolver works.
    """
    path = mock_file_path("gedcom_1.ged")
    assert path.is_file(), f"Expected GEDCOM file at: {path}"


def test_segment_records_builds_top_level_records() -> None:
    """
    Test: segment_records must return a list of level-0 GEDCOMNode objects.

    The first record of a valid GEDCOM file must be HEAD.
    All records returned must have level == 0.
    """
    path = mock_file_path("gedcom_1.ged")
    tokens = list(tokenize_file(path))
    assert tokens, "Tokenizer returned no tokens"

    records = list(segment_records(tokens))
    assert records, "Segmenter returned no top-level records"

    # First record should be HEAD
    first = records[0]
    assert first.level == 0
    assert first.tag == "HEAD"

    # All segment_records outputs must be level-0 nodes
    assert all(r.level == 0 for r in records)
