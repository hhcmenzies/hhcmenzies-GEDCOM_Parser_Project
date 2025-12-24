
from gedcom_parser.registry.build_individual import build_individual
from gedcom_parser.loader.tree_builder import GEDCOMNode


def make_node(tag, value=None, pointer=None, children=None):
    return GEDCOMNode(
        tag=tag,
        value=value,
        pointer=pointer,
        children=children or [],
        lineno=1,
        level=0,
    )


def test_build_individual_basic():
    indi = make_node(
        "INDI",
        pointer="@I1@",
        children=[
            make_node(
                "NAME",
                value="John /Doe/",
                children=[
                    make_node("GIVN", "John"),
                    make_node("SURN", "Doe"),
                ],
            ),
            make_node("SEX", "M"),
            make_node("FAMS", pointer="@F1@"),
            make_node("FAMC", pointer="@F2@"),
            make_node("OCCU", "Farmer"),
        ],
    )

    entity = build_individual(indi)

    assert entity.pointer == "@I1@"
    assert entity.uuid
    assert entity.gender == "M"

    assert len(entity.names) == 1
    assert entity.names[0].given == "John"
    assert entity.names[0].surname == "Doe"

    assert "@F1@" in entity.families_as_spouse
    assert "@F2@" in entity.families_as_child

    # OCCU preserved as GenericAttribute
    tags = [a.tag for a in entity.attributes]
    assert "OCCU" in tags
