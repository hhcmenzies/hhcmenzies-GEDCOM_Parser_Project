from gedcom_parser.registry.entities import GedcomRegistry, IndividualEntity, FamilyEntity
from gedcom_parser.registry.link_entities import link_entities


def test_spouse_relationships_linked():
    reg = GedcomRegistry()
    h = IndividualEntity(uuid="u-h", pointer="@I1@")
    w = IndividualEntity(uuid="u-w", pointer="@I2@")
    f = FamilyEntity(uuid="u-f", pointer="@F1@", husband="@I1@", wife="@I2@")

    reg.register_individual(h)
    reg.register_individual(w)
    reg.register_family(f)

    link_entities(reg)

    assert f.husband_entity is h
    assert f.wife_entity is w
    assert f in h.spouse_in_families
    assert f in w.spouse_in_families


def test_child_relationships_linked():
    reg = GedcomRegistry()
    c = IndividualEntity(uuid="u-c", pointer="@I3@")
    f = FamilyEntity(uuid="u-f", pointer="@F1@", children=["@I3@"])

    reg.register_individual(c)
    reg.register_family(f)

    link_entities(reg)

    assert c in f.children_entities
    assert f in c.child_in_families


def test_missing_references_do_not_crash():
    reg = GedcomRegistry()
    # Family references individuals that do not exist in registry
    f = FamilyEntity(uuid="u-f", pointer="@F1@", husband="@I404@", children=["@I999@"])
    reg.register_family(f)

    link_entities(reg)  # should not raise

    assert f.husband_entity is None
    assert f.children_entities == []

