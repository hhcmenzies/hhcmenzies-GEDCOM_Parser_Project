
from gedcom_parser.registry.build_note import build_note
from gedcom_parser.loader.tree_builder import GEDCOMNode


def make_node(tag, value=None, pointer=None, children=None, level=0):
    return GEDCOMNode(
        level=level,
        tag=tag,
        value=value,
        pointer=pointer,
        children=children or [],
    )


def test_build_note_basic_and_multiline():
    note = make_node(
        "NOTE",
        pointer="@N1@",
        value="This is the first line.",
        children=[
            # Newline continuation
            make_node("CONT", "This is a second line.", level=1),
            # Concatenation continuation (no newline)
            make_node("CONC", " And this is appended.", level=1),
            # Another newline continuation
            make_node("CONT", "Third line.", level=1),
            # Custom/unmodeled tag should be preserved
            make_node("_FOO", "bar", level=1),
        ],
    )

    entity = build_note(note)

    assert entity.pointer == "@N1@"

    # We expect the NOTE builder to return a single text blob that respects
    # CONT as newline and CONC as inline append.
    assert entity.text.startswith("This is the first line.")
    assert "This is a second line." in entity.text
    assert "And this is appended." in entity.text
    assert "Third line." in entity.text

    # Custom tags preserved
    assert any(a.tag == "_FOO" for a in entity.attributes)
