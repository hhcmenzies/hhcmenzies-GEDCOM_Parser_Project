from gedcom_parser.registry.build_source import build_source
from gedcom_parser.loader.tree_builder import GEDCOMNode


def make_node(tag, value=None, pointer=None, children=None):
    return GEDCOMNode(
        level=0,
        tag=tag,
        value=value,
        pointer=pointer,
        children=children or [],
    )


def test_build_source_basic():
    sour = make_node(
        "SOUR",
        pointer="@S1@",
        children=[
            make_node("TITL", "Massachusetts Birth Records"),
            make_node("AUTH", "Ancestry.com"),
            make_node("PUBL", "Ancestry.com Operations Inc"),
            make_node("_APID", "1,1234::0"),
            make_node("REPO", pointer="@R1@"),
            make_node("NOTE", "Some long explanatory note"),
        ],
    )

    entity = build_source(sour)

    assert entity.pointer == "@S1@"
    assert entity.title == "Massachusetts Birth Records"
    assert entity.author == "Ancestry.com"
    assert entity.publication == "Ancestry.com Operations Inc"
    assert entity.repository_pointer == "@R1@"
    assert "Some long explanatory note" in entity.notes

    # Custom tags preserved
    assert any(a.tag == "_APID" for a in entity.attributes)
