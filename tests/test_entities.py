from pathlib import Path

from gedcom_parser.loader import (
    tokenize_file,
    build_tree,
    reconstruct_values,
    segment_top_level,
)
from gedcom_parser.entities.registry import build_entity_registry

DATA_DIR = Path(__file__).resolve().parent.parent / "mock_files"


def test_entity_registry_counts_match_sections():
    tokens = list(tokenize_file(str(DATA_DIR / "gedcom_1.ged")))
    tree = build_tree(tokens)
    tree = reconstruct_values(tree)

    sections = segment_top_level(tree)
    registry = build_entity_registry(tree)

    assert len(registry.individuals) == len(sections.get("INDI", []))
    assert len(registry.families) == len(sections.get("FAM", []))
    assert len(registry.sources) == len(sections.get("SOUR", []))
    assert len(registry.repositories) == len(sections.get("REPO", []))
    assert len(registry.media_objects) == len(sections.get("OBJE", []))


def test_entity_registry_sample_individual():
    tokens = list(tokenize_file(str(DATA_DIR / "gedcom_1.ged")))
    tree = build_tree(tokens)
    tree = reconstruct_values(tree)
    registry = build_entity_registry(tree)

    # We expect at least one individual in any real GEDCOM file
    assert registry.individuals

    # Grab one pointer and make sure the entity is wired correctly
    sample_ptr = next(iter(registry.individuals.keys()))
    entity = registry.get_individual(sample_ptr)

    assert entity is not None
    assert entity.pointer == sample_ptr
    assert entity.root.get("tag") == "INDI"
