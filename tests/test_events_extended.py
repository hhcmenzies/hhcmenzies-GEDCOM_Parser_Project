# tests/test_events_extended.py

from __future__ import annotations

from gedcom_parser.events.event import (
    extract_event,
    extract_events_from_record,
    EventRole,
)


def test_roles_from_family_record_husb_wife_child():
    fam = {
        "tag": "FAM",
        "children": [
            {"tag": "HUSB", "pointer": "@I1@"},
            {"tag": "WIFE", "pointer": "@I2@"},
            {"tag": "CHIL", "pointer": "@I3@"},
            {
                "tag": "MARR",
                "children": [
                    {"tag": "DATE", "value": "1 JAN 1900"},
                ],
            },
        ],
    }

    events = extract_events_from_record(fam, record_uuid="F1")
    assert events, "Expected at least one family event"
    marr = [e for e in events if e.tag == "MARR"][0]

    role_tags = {r.tag for r in marr.roles}
    role_values = {r.value for r in marr.roles}

    assert role_tags == {"HUSB", "WIFE", "CHIL"}
    assert role_values == {"@I1@", "@I2@", "@I3@"}


def test_roles_from_event_children_asso_and_role():
    node = {
        "tag": "EVEN",
        "children": [
            {"tag": "ROLE", "value": "Witness"},
            {"tag": "ASSO", "pointer": "@I5@"},
        ],
    }

    evt = extract_event(node, record_uuid="I1")
    role_tags = {r.tag for r in evt.roles}
    assert role_tags == {"ROLE", "ASSO"}

    assoc = [r for r in evt.roles if r.tag == "ASSO"][0]
    assert assoc.value == "@I5@"


def test_custom_role_tag_witn_like():
    fam = {
        "tag": "FAM",
        "children": [
            {"tag": "HUSB", "pointer": "@I1@"},
            {
                "tag": "MARR",
                "children": [
                    {"tag": "DATE", "value": "1900"},
                ],
            },
            {"tag": "_WITN", "pointer": "@I50@"},
        ],
    }

    events = extract_events_from_record(fam, record_uuid="F1")
    marr = [e for e in events if e.tag == "MARR"][0]

    role_tags = {r.tag for r in marr.roles}
    assert "_WITN" in role_tags

    witn = [r for r in marr.roles if r.tag == "_WITN"][0]
    assert witn.value == "@I50@"


def test_place_normalization_basic():
    node = {
        "tag": "BIRT",
        "children": [
            {"tag": "DATE", "value": "1900"},
            {"tag": "PLAC", "value": "  New   York ,   USA  "},
        ],
    }

    evt = extract_event(node, record_uuid="I1")
    assert evt.place == "New York, USA"


def test_multiple_notes_preserved():
    node = {
        "tag": "EVEN",
        "children": [
            {"tag": "NOTE", "value": "First note line"},
            {"tag": "NOTE", "value": "Second note\nwith newline"},
        ],
    }

    evt = extract_event(node, record_uuid="I1")
    assert len(evt.notes) == 2
    assert "First note line" in evt.notes[0]
    assert "Second note" in evt.notes[1]
