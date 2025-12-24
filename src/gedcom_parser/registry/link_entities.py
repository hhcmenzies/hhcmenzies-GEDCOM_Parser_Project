from __future__ import annotations

from typing import Optional

from gedcom_parser.identity.uuid_factory import normalize_pointer
from gedcom_parser.registry.entities import GedcomRegistry, FamilyEntity, IndividualEntity


def _norm_ptr(ptr: Optional[str]) -> Optional[str]:
    if not ptr:
        return None
    return normalize_pointer(ptr) or ptr


def link_entities(registry: GedcomRegistry) -> None:
    """
    Phase 4.3: Cross-entity relationship linking.

    Design:
      - builders remain pure
      - registry is built first
      - this pass resolves pointers into object references

    Idempotent:
      - clears derived fields before rebuilding them
    """
    # Clear derived fields on individuals
    for ind in registry.individuals.values():
        ind.spouse_in_families.clear()
        ind.child_in_families.clear()

    # Clear derived fields on families
    for fam in registry.families.values():
        fam.husband_entity = None
        fam.wife_entity = None
        fam.children_entities.clear()

    # Build links
    for fam in registry.families.values():
        husb_ptr = _norm_ptr(fam.husband)
        wife_ptr = _norm_ptr(fam.wife)

        if husb_ptr:
            husb = registry.individuals.get(husb_ptr)
            if husb is not None:
                fam.husband_entity = husb
                husb.spouse_in_families.append(fam)

        if wife_ptr:
            wife = registry.individuals.get(wife_ptr)
            if wife is not None:
                fam.wife_entity = wife
                wife.spouse_in_families.append(fam)

        for cptr in fam.children:
            child_ptr = _norm_ptr(cptr)
            if not child_ptr:
                continue
            child = registry.individuals.get(child_ptr)
            if child is None:
                continue
            fam.children_entities.append(child)
            child.child_in_families.append(fam)

