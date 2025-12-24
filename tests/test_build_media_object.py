from gedcom_parser.registry.build_media_object import build_media_object


def make_node(tag, value=None, pointer=None, children=None, level=0):
    # Minimal stand-in for your GEDCOMNode test helper style.
    class N:
        def __init__(self):
            self.tag = tag
            self.value = value
            self.pointer = pointer
            self.children = children or []
            self.lineno = None
            self.level = level

    return N()


def test_build_media_object_basic():
    obje = make_node(
        "OBJE",
        pointer="@O1@",
        children=[
            make_node(
                "FILE",
                value="photos/david.jpg",
                children=[
                    make_node(
                        "FORM",
                        value="jpg",
                        children=[make_node("TYPE", value="photo")],
                    )
                ],
            ),
            make_node("TITL", value="Profile photo"),
            make_node("_PRIM", value="Y"),
        ],
    )

    entity = build_media_object(obje)

    assert entity.pointer == "@O1@"
    assert entity.title == "Profile photo"
    assert len(entity.files) == 1
    assert entity.files[0].path == "photos/david.jpg"
    assert entity.files[0].form == "jpg"
    assert entity.files[0].media_type == "photo"

    # Unmodeled tag preserved
    assert any(a.tag == "_PRIM" and a.value == "Y" for a in entity.attributes)
