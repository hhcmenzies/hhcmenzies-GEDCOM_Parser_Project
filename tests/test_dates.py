# tests/test_dates.py

from __future__ import annotations

from gedcom_parser.dates.normalizer import parse_date


def test_simple_year():
    d = parse_date("1900")
    assert d["normalized"] == "1900"
    assert d["precision"] == "year"
    assert d["kind"] == "exact"
    assert d["date"] == "1900"


def test_month_year():
    d = parse_date("JAN 1900")
    assert d["normalized"] == "1900-01"
    assert d["precision"] == "month"
    assert d["kind"] == "exact"
    assert d["date"] == "1900-01"


def test_full_date():
    d = parse_date("1 JAN 1900")
    assert d["normalized"] == "1900-01-01"
    assert d["precision"] == "day"
    assert d["kind"] == "exact"
    assert d["date"] == "1900-01-01"


def test_approximate_abt():
    d = parse_date("ABT 1900")
    assert d["modifier"] == "ABT"
    assert d["kind"] == "approximate"
    assert d["normalized"] == "1900"
    assert d["date"] == "1900"


def test_approximate_circa_alias():
    d = parse_date("circa 1850")
    assert d["modifier"] == "ABT"
    assert d["kind"] == "approximate"
    assert d["date"] == "1850"


def test_before_date():
    d = parse_date("BEF 1800")
    assert d["modifier"] == "BEF"
    assert d["kind"] == "before"
    # We at least expect the base date to be normalized correctly
    assert d["date"] == "1800"


def test_after_date_alias():
    d = parse_date("after 1750")
    assert d["modifier"] == "AFT"
    assert d["kind"] == "after"
    assert d["date"] == "1750"


def test_between_range():
    d = parse_date("BET 1 JAN 1800 AND 2 FEB 1810")
    assert d["kind"] == "range"
    assert d["modifier"] == "BET"
    assert d["start"] == "1800-01-01"
    assert d["end"] == "1810-02-02"


def test_from_to_range():
    d = parse_date("FROM 1900 TO 1910")
    assert d["kind"] == "range"
    assert d["modifier"] == "FROM"
    assert d["start"] == "1900"
    assert d["end"] == "1910"


def test_seasonal_spring():
    d = parse_date("spring 1880")
    assert d["kind"] == "seasonal"
    assert d["season"] == "SPRING"
    assert d["date"] == "1880"
    assert d["precision"] == "year"


def test_calendar_suffix_julian():
    d = parse_date("1 JAN 1750 (Julian)")
    assert d["calendar"] == "JULIAN"
    assert d["normalized"] == "1750-01-01"


def test_unknown_date_string():
    d = parse_date("Unknown")
    # We don't try to normalize arbitrary strings; just maintain them.
    assert d["kind"] in ("unknown", "exact", "seasonal")  # keep it loose
    assert d["raw"] == "Unknown"
