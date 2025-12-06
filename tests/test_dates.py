from gedcom_parser.dates.normalizer import parse_gedcom_date

def test_simple_year():
    d = parse_gedcom_date("1699")
    assert d["kind"] == "simple"
    assert d["normalized"] == "1699-01-01"
    assert d["year"] == 1699

def test_day_month_year():
    d = parse_gedcom_date("14 Jul 1684")
    assert d["kind"] == "simple"
    assert d["normalized"] == "1684-07-14"
    assert d["day"] == 14
    assert d["month"] == 7

def test_month_year():
    d = parse_gedcom_date("Jul 1684")
    assert d["kind"] == "simple"
    assert d["normalized"] == "1684-07-01"

def test_about():
    d = parse_gedcom_date("Abt. 1694")
    assert d["kind"] == "about"
    assert d["normalized"] == "1694-01-01"

def test_before():
    d = parse_gedcom_date("BEF 1700")
    assert d["kind"] == "before"
    assert d["end"] == "1700-01-01"

def test_after():
    d = parse_gedcom_date("AFT 1700")
    assert d["kind"] == "after"
    assert d["start"] == "1700-01-01"

def test_range_between():
    d = parse_gedcom_date("BET 1690 AND 1695")
    assert d["kind"] == "between"
    assert d["start"] == "1690-01-01"
    assert d["end"] == "1695-01-01"

def test_range_from_to():
    d = parse_gedcom_date("FROM 1690 TO 1695")
    assert d["kind"] == "from_to"
    assert d["start"] == "1690-01-01"
    assert d["end"] == "1695-01-01"

def test_garbage():
    d = parse_gedcom_date("Some garbage date")
    assert d["kind"] == "unknown"
    assert d["normalized"] is None
