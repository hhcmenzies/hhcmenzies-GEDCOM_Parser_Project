# src/gedcom_parser/validation/pointer_validator.py

from typing import Dict, List
from .models import ValidationIssue

def validate_pointers(
    registry,
    tag_defs: Dict[str, dict],
) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []

    # Build lookup: xref -> record tag
    record_types = {
        rec.xref: rec.tag
        for rec in registry.all_records()
        if rec.xref
    }

    for rec in registry.all_records():
        for ref in rec.raw_pointers:  # ← IMPORTANT (see section 6)
            tag = ref.tag
            value = ref.value
            line = ref.line

            tag_def = tag_defs.get(tag)

            # 1. Pointer where none expected
            if not tag_def or tag_def["payload"] != "pointer":
                issues.append(ValidationIssue(
                    severity="ERROR",
                    code="GEDCOM.PTR.UNEXPECTED_POINTER",
                    message=f"Tag '{tag}' does not accept a pointer value",
                    line=line,
                    xref=rec.xref,
                    tag=tag,
                ))
                continue

            # 2. Format check
            if not (value.startswith("@") and value.endswith("@")):
                issues.append(ValidationIssue(
                    severity="ERROR",
                    code="GEDCOM.PTR.FORMAT_INVALID",
                    message=f"Invalid pointer format '{value}'",
                    line=line,
                    xref=rec.xref,
                    tag=tag,
                ))
                continue

            target = value.strip("@")

            # 3. Target exists
            if target not in record_types:
                issues.append(ValidationIssue(
                    severity="ERROR",
                    code="GEDCOM.PTR.TARGET_MISSING",
                    message=f"Pointer '{value}' does not resolve to any record",
                    line=line,
                    xref=rec.xref,
                    tag=tag,
                ))
                continue

            # 4. Target type matches expectation
            expected = tag_def.get("pointer_to")
            actual = record_types[target]

            if expected and actual != expected:
                issues.append(ValidationIssue(
                    severity="ERROR",
                    code="GEDCOM.PTR.TARGET_WRONG_TYPE",
                    message=(
                        f"Pointer '{value}' resolves to '{actual}', "
                        f"but '{tag}' requires '{expected}'"
                    ),
                    line=line,
                    xref=rec.xref,
                    tag=tag,
                ))

    return issues
