import json
from pathlib import Path

import pytest
pytestmark = pytest.mark.xfail(reason="Requires entity builders (Phase 4.2+)")

from gedcom_parser.loader import tokenize_file, build_tree, reconstruct_values
from gedcom_parser.entities.registry import build_entity_registry
from gedcom_parser.identity.uuid_factory import (
    uuid_for_pointer,
    uuid_for_name,
    uuid_for_event,
    uuid_for_occupation,
)

DATA_DIR = Path("GEDCOM_Parser_OLD/mock_files")


def test_entity_uuid_determinism():
    ged_path = DATA_DIR / "gedcom_1.ged"
    tokens = list(tokenize_file(str(ged_path)))
    tree = reconstruct_values(build_tree(tokens))
    reg = build_entity_registry(tree)

    # Grab one INDI and one FAM to assert deterministic UUIDs
    assert reg.individuals, "No individuals found"
    ptr, indi = next(iter(reg.individuals.items()))
    facts = indi.facts

    # Record-level UUID should exist
    assert "uuid" in facts
    first_uuid = facts["uuid"]
    assert isinstance(first_uuid, str) and len(first_uuid) == 36

    # Recompute UUID from pointer and compare
    recomputed = uuid_for_pointer("INDI", ptr)
    assert recomputed == first_uuid


def test_name_and_event_uuids():
    ged_path = DATA_DIR / "gedcom_1.ged"
    tokens = list(tokenize_file(str(ged_path)))
    tree = reconstruct_values(build_tree(tokens))
    reg = build_entity_registry(tree)

    ptr, indi = next(iter(reg.individuals.items()))
    facts = indi.facts
    indi_uuid = facts["uuid"]

    nb = facts.get("name_block")
    assert nb is not None
    assert "uuid" in nb
    assert len(nb["uuid"]) == 36

    full_norm = nb.get("full_name_normalized") or ""
    recomputed_name_uuid = uuid_for_name(indi_uuid, full_norm)
    assert recomputed_name_uuid == nb["uuid"]

    events = facts.get("events", {})
    if events:
        etag, ev = next(iter(events.items()))
        assert "uuid" in ev
        raw_date = ev.get("date") or ""
        raw_place = ""
        if isinstance(ev.get("place"), dict):
            raw_place = ev["place"].get("raw") or ""
        elif ev.get("plac"):
            raw_place = ev["plac"] or ""
        recomputed_event_uuid = uuid_for_event(indi_uuid, etag, raw_date, raw_place)
        assert recomputed_event_uuid == ev["uuid"]


def test_occupation_uuid():
    ged_path = DATA_DIR / "gedcom_1.ged"
    tokens = list(tokenize_file(str(ged_path)))
    tree = reconstruct_values(build_tree(tokens))
    reg = build_entity_registry(tree)

    # Find any individual with a non-empty occupation list
    for ptr, indi in reg.individuals.items():
        facts = indi.facts
        occ = facts.get("occupation", {})
        all_occ = occ.get("all") or []
        if not all_occ:
            continue

        indi_uuid = facts["uuid"]
        assert "uuid" in occ
        occ_uuid = occ["uuid"]
        assert len(occ_uuid) == 36

        recomputed = uuid_for_occupation(indi_uuid, occ)
        assert recomputed == occ_uuid
        break
