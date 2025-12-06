from gedcom_parser.loader import (
    tokenize_file,
    build_tree,
    reconstruct_values,
    segment_top_level,
    summarize_top_level,
    build_pointer_index,
    summarize_pointer_prefixes,
)


def test_segment_and_pointers_smoke():
    tokens = list(
        tokenize_file("GEDCOM_Parser_OLD/mock_files/gedcom_1.ged")
    )
    tree = build_tree(tokens)
    tree = reconstruct_values(tree)

    sections = segment_top_level(tree)
    summary = summarize_top_level(tree)
    ptr_index = build_pointer_index(tree)
    prefix_summary = summarize_pointer_prefixes(ptr_index)

    # Basic sanity checks: we expect at least some INDI/FAM/SOUR/REPO/etc.
    assert len(tree) > 0
    assert isinstance(sections, dict)
    assert isinstance(summary, dict)
    assert isinstance(ptr_index, dict)
    assert isinstance(prefix_summary, dict)

    # Most realistic GEDCOMs have individuals and families
    assert "INDI" in sections
    assert "FAM" in sections
