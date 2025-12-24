# tests/test_events.py

from __future__ import annotations

from gedcom_parser.events.event import (
    extract_event,
    extract_events_from_record,
    is_event_tag,
    is_family_event_tag,
)
from gedcom_parser.dates.normalizer import parse_date


def test_is_event_tag_individual_and_family():
    assert is_event_tag("BIRT") is True
    assert is_event_tag("MARR") is True
    assert is_event_tag("XYZ") is False


def test_is_family_event_tag():
    assert is_family_event_tag("MARR") is True
    assert is_family_event_tag("BIRT") is False


def test_extract_event_basic():
    node = {
        "tag": "BIRT",
        "value": "A birth event",
        "children": [
            {"tag": "DATE", "value": "1 JAN 1900"},
            {"tag": "PLAC", "value": "New York"},
            {"tag": "NOTE", "value": "Born in winter"},
        ],
        "lineno": 12,
    }

    evt = extract_event(node, record_uuid="I1")
    assert evt.tag == "BIRT"
    assert evt.uuid.startswith("evt-I1-BIRT")
    assert evt.date["normalized"] == "1900-01-01"
    assert evt.place == "New York"
    assert "Born in winter" in evt.notes


def test_extract_events_from_record():
    record = {
        "tag": "FAM",
        "children": [
            {"tag": "MARR", "children": [{"tag": "DATE", "value": "1900"}]},
            {"tag": "DIV", "children": [{"tag": "DATE", "value": "1930"}]},
        ],
    }

    events = extract_events_from_record(record, record_uuid="F9")
    tags = {e.tag for e in events}
    assert tags == {"MARR", "DIV"}
    assert events[0].uuid.startswith("evt-F9")
