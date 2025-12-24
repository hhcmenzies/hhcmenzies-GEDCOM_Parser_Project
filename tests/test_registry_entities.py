# tests/test_registry_entities.py

from __future__ import annotations

from gedcom_parser.registry.entities import (
    GedcomRegistry,
    IndividualEntity,
    FamilyEntity,
    SourceEntity,
    NoteEntity,
    NameRecord,
    GenericAttribute,
)
from gedcom_parser.events.event import Event


def test_registry_accepts_and_returns_individual():
    reg = GedcomRegistry()
    ind = IndividualEntity(uuid="indi-I1", pointer="@I1@")
    reg.register_individual(ind)

    assert reg.get_individual("@I1@") is ind


def test_family_registration_and_lookup():
    reg = GedcomRegistry()
    fam = FamilyEntity(uuid="fam-F1", pointer="@F1@")
    reg.register_family(fam)

    assert reg.get_family("@F1@") is fam


def test_source_and_note_entities_register_properly():
    reg = GedcomRegistry()
    src = SourceEntity(uuid="src-S1", pointer="@S1@", title="Book")
    note = NoteEntity(uuid="note-N1", pointer="@N1@", text="A note")

    reg.register_source(src)
    reg.register_note(note)

    assert reg.get_source("@S1@").title == "Book"
    assert reg.get_note("@N1@").text == "A note"


def test_individual_supports_names_events_and_attributes():
    ind = IndividualEntity(uuid="indi-I2", pointer="@I2@")

    ind.names.append(NameRecord(full="John /Doe/"))
    ind.events.append(Event(uuid="evt-I2-BIRT", tag="BIRT"))
    ind.attributes.append(GenericAttribute(tag="OCCU", value="Farmer"))

    assert len(ind.names) == 1
    assert len(ind.events) == 1
    assert ind.attributes[0].tag == "OCCU"
