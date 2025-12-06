from gedcom_parser.loader.value_reconstructor import reconstruct_values

def test_conc_cont_merge():
    node = {
        "level": 1,
        "tag": "NOTE",
        "value": "Line1",
        "pointer": None,
        "lineno": 1,
        "children": [
            {"level": 2, "tag": "CONC", "value": "X", "children": [], "pointer": None, "lineno": 2},
            {"level": 2, "tag": "CONT", "value": "Line2", "children": [], "pointer": None, "lineno": 3},
            {"level": 2, "tag": "CONC", "value": "Y", "children": [], "pointer": None, "lineno": 4},
        ]
    }

    tree = reconstruct_values([node])

    assert tree[0]["value"] == "Line1X\nLine2Y"
