from gedcom_parser.loader.tokenizer import tokenize_line

def test_tokenize_line():
    t = tokenize_line("1 NAME John /Doe/")
    assert t["level"] == 1
    assert t["tag"] == "NAME"
    assert t["value"] == "John /Doe/"
