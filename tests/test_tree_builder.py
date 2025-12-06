from gedcom_parser.loader.tree_builder import build_tree
from gedcom_parser.loader.tokenizer import tokenize_line

def test_tree_builder():
    # Sample record
    lines = [
        "0 @I1@ INDI",
        "1 NAME John /Doe/",
        "2 GIVN John",
        "2 SURN Doe",
        "1 BIRT",
        "2 DATE 1 JAN 1900"
    ]

    tokens = [tokenize_line(l) for l in lines]
    for i, t in enumerate(tokens):
        t["lineno"] = i + 1

    tree = build_tree(tokens)

    assert len(tree) == 1
    assert tree[0]["tag"] == "INDI"
    assert len(tree[0]["children"]) > 0
