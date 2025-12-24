# tests/test_events_enriched.py

from __future__ import annotations

from gedcom_parser.events.event import extract_event, extract_events_from_record


def test_cause_and_certainty_extracted_for_death_event():
    record = {
        "tag": "INDI",
        "children": [
            {
                "tag": "DEAT",
                "children": [
                    {"tag": "DATE", "value": "1 JAN 1950"},
                    {"tag": "CAUS", "value": "Heart attack"},
                    {"tag": "QUAY", "value": "3"},
                ],
            },
        ],
    }

    events = extract_events_from_record(record, record_uuid="I1")
    assert events, "Expected at least one event"
    deat = [e for e in events if e.tag == "DEAT"][0]

    assert deat.cause == "Heart attack"
    assert deat.certainty == 3


def test_age_at_event_from_birth_and_death():
    record = {
        "tag": "INDI",
        "children": [
            {
                "tag": "BIRT",
                "children": [
                    {"tag": "DATE", "value": "1 JAN 1900"},
                ],
            },
            {
                "tag": "DEAT",
                "children": [
                    {"tag": "DATE", "value": "1 JAN 1950"},
                ],
            },
        ],
    }

    events = extract_events_from_record(record, record_uuid="I1")
    deat = [e for e in events if e.tag == "DEAT"][0]

    assert deat.age is not None
    assert deat.age["years"] == 50
    assert deat.age["approximate"] is False


def test_even_type_and_description():
    node = {
        "tag": "EVEN",
        "value": "Promoted to Captain",
        "children": [
            {"tag": "TYPE", "value": "Military Promotion"},
        ],
    }

    evt = extract_event(node, record_uuid="I1")
    assert evt.type == "Event"
    assert evt.description == "Promoted to Captain"
    assert evt.subtype == "Military Promotion"


def test_location_from_map_coordinates():
    node = {
        "tag": "BIRT",
        "children": [
            {"tag": "DATE", "value": "1900"},
            {"tag": "PLAC", "value": "Somewhere"},
            {
                "tag": "MAP",
                "children": [
                    {"tag": "LATI", "value": "N45.123"},
                    {"tag": "LONG", "value": "W93.456"},
                ],
            },
        ],
    }

    evt = extract_event(node, record_uuid="I1")
    assert evt.location is not None
    assert abs(evt.location["latitude"] - 45.123) < 1e-6
    assert abs(evt.location["longitude"] + 93.456) < 1e-6  # west is negative


def test_role_normalization_labels():
    fam = {
        "tag": "FAM",
        "children": [
            {"tag": "HUSB", "pointer": "@I1@"},
            {"tag": "WIFE", "pointer": "@I2@"},
            {"tag": "_WITN", "pointer": "@I50@"},
            {
                "tag": "MARR",
                "children": [
                    {"tag": "DATE", "value": "1 JAN 1900"},
                ],
            },
        ],
    }

    events = extract_events_from_record(fam, record_uuid="F1")
    marr = [e for e in events if e.tag == "MARR"][0]

    labels = {r.normalized for r in marr.roles}
    assert "Husband" in labels
    assert "Wife" in labels
    assert "Witness" in labels
