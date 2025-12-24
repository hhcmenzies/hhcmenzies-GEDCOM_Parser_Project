# tests/test_reconstruct_values.py

from __future__ import annotations

from gedcom_parser.loader import tokenize_file, build_tree, reconstruct_values
from gedcom_parser.utils import mock_file_path
from gedcom_parser.loader.segmenter import GEDCOMNode


def test_conc_appends_without_newline():
    # Build a fake record tree with CONT/CONC mixture
    parent = GEDCOMNode(level=1, tag="NOTE", value="Line one", pointer=None, lineno=1)
    conc = GEDCOMNode(level=2, tag="CONC", value=" and more", pointer=None, lineno=2)
    cont = GEDCOMNode(level=2, tag="CONT", value="Second line", pointer=None, lineno=3)
    conc2 = GEDCOMNode(level=2, tag="CONC", value=" more text", pointer=None, lineno=4)

    parent.children = [conc, cont, conc2]

    reconstruct_values([parent])

    # Expected:
    #   "Line one and more\nSecond line more text"
    expected = "Line one and more\nSecond line more text"
    assert parent.value == expected

    # CONC/CONT nodes should be removed
    assert parent.children == []


def test_reconstruct_values_on_real_file_runs_without_error():
    """
    Basic smoke test: reconstructing the values of a real GEDCOM tree
    should run without exceptions and not remove top-level structure.
    """
    path = mock_file_path("gedcom_1.ged")
    tokens = list(tokenize_file(str(path)))
    tree = build_tree(tokens)

    before_count = len(tree.records)

    reconstruct_values(tree.records)

    after_count = len(tree.records)

    assert before_count == after_count, "Reconstruction must not alter top-level structure"


def test_reconstruction_preserves_children_structure():
    """
    Ensure that non-CONC/CONT child nodes remain intact.
    """
    parent = GEDCOMNode(level=1, tag="NOTE", value="Base", lineno=1, pointer=None)
    child_event = GEDCOMNode(level=2, tag="DATE", value="1900", lineno=2, pointer=None)
    conc = GEDCOMNode(level=2, tag="CONC", value=" extra", lineno=3, pointer=None)

    parent.children = [child_event, conc]

    reconstruct_values([parent])

    assert parent.value == "Base extra"
    assert len(parent.children) == 1
    assert parent.children[0].tag == "DATE"
