from gedcom_parser.registry.build_family import build_family
from gedcom_parser.loader.tree_builder import GEDCOMNode


def make_node(tag, value=None, pointer=None, children=None, level=0, lineno=1):
    return GEDCOMNode(
        tag=tag,
        value=value,
        pointer=pointer,
        children=children or [],
        lineno=lineno,
        level=level,
    )


def test_build_family_basic():
    fam = make_node(
        "FAM",
        pointer="@F1@",
        children=[
            make_node("HUSB", pointer="@I1@", level=1),
            make_node("WIFE", pointer="@I2@", level=1),
            make_node("CHIL", pointer="@I3@", level=1),
            make_node("NOTE", value="Married in town hall", level=1),
            make_node("SOUR", pointer="@S1@", level=1),
            make_node("NCHI", value="1", level=1),  # should land in attributes
        ],
    )

    entity = build_family(fam)

    assert entity.pointer == "@F1@"
    assert entity.uuid
    assert entity.husband == "@I1@"
    assert entity.wife == "@I2@"
    assert "@I3@" in entity.children
    assert "Married in town hall" in entity.notes
    assert "@S1@" in entity.sources

    # Lossless: NCHI should be preserved as GenericAttribute
    assert any(a.tag == "NCHI" and a.value == "1" for a in entity.attributes)
