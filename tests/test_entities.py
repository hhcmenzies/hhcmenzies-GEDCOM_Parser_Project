# tests/test_entities.py
import json
from pathlib import Path

import pytest
pytestmark = pytest.mark.xfail(reason="Requires GEDCOMNode → Entity extraction (Phase 4.2)")

from gedcom_parser.loader.tokenizer import tokenize_file
from gedcom_parser.loader.segmenter import segment_lines
from gedcom_parser.loader.tree_builder import build_tree
from gedcom_parser.entities.registry import build_entity_registry


DATA_DIR = Path("tests/data")
GED_PATH = DATA_DIR / "gedcom_1.ged"


def test_entity_registry_counts_match_sections():
    tokens = list(tokenize_file(str(GED_PATH)))
    segments = segment_lines(tokens)
    tree = build_tree(segments)

    registry = build_entity_registry(tree)

    assert "individuals" in registry
    assert "families" in registry
    assert "sources" in registry
    assert "repositories" in registry
    assert "media_objects" in registry

    assert registry["individuals"]  # must not be empty
    assert registry["families"]     # must not be empty


def test_entity_registry_sample_individual():
    tokens = list(tokenize_file(str(GED_PATH)))
    segments = segment_lines(tokens)
    tree = build_tree(segments)

    registry = build_entity_registry(tree)

    sample_id = next(iter(registry["individuals"]))
    sample = registry["individuals"][sample_id]

    assert isinstance(sample, dict)
    assert "events" in sample
    assert "names" in sample
