# tests/test_tree_builder.py

from __future__ import annotations

from gedcom_parser.loader import GEDCOMTree, tokenize_file, build_tree
from gedcom_parser.utils import mock_file_path


def test_build_tree_returns_gedcom_tree_instance() -> None:
    """
    Smoke test: build_tree should return a GEDCOMTree with at least one record.
    """
    path = mock_file_path("gedcom_1.ged")
    tokens = list(tokenize_file(str(path)))
    tree = build_tree(tokens)

    assert isinstance(tree, GEDCOMTree)
    assert tree.records, "Expected at least one top-level record in the tree"


def test_tree_first_record_is_head_and_level_zero() -> None:
    """
    For a valid GEDCOM file, the first record should be the HEAD record at level 0.
    """
    path = mock_file_path("gedcom_1.ged")
    tokens = list(tokenize_file(str(path)))
    tree = build_tree(tokens)

    first = tree.records[0]
    assert first.level == 0
    assert first.tag == "HEAD"


def test_tree_pointer_lookup_round_trip() -> None:
    """
    If there are any pointer-bearing records (e.g. @I1@ INDI),
    find_by_pointer should return the same node object.
    """
    path = mock_file_path("gedcom_1.ged")
    tokens = list(tokenize_file(str(path)))
    tree = build_tree(tokens)

    # Find the first node in the tree with a non-empty pointer
    target = None
    for node in tree.iter_nodes():
        if node.pointer:
            target = node
            break

    if target is None:
        # File has no pointers; nothing more to assert here.
        return

    found = tree.find_by_pointer(target.pointer)
    assert found is not None
    assert found is target  # same object identity


def test_tree_head_records_lookup_by_tag() -> None:
    """
    find_records_by_tag should return the HEAD record(s) when asked.
    """
    path = mock_file_path("gedcom_1.ged")
    tokens = list(tokenize_file(str(path)))
    tree = build_tree(tokens)

    heads = tree.find_records_by_tag("HEAD")
    assert heads, "Expected at least one HEAD record"
    assert all(rec.level == 0 for rec in heads)
    assert all(rec.tag == "HEAD" for rec in heads)
