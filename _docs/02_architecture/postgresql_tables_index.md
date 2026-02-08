# PostgreSQL Tables Index

This is the index of tables the system expects, organized by layer.
This document is authoritative for naming and responsibility; SQL implementations must match it.

## Control Plane
- ingestion_run: defines a single deterministic processing run
- ingested_file: records discovered inputs with hashes
- run_issue: records warnings/errors by stage and severity

## Raw Layer
- gedcom_raw_node: lossless GEDCOM tree capture (level/tag/value/pointers/parent)
- gedcom_raw_line (optional): raw line capture for full traceability

## Canonical Layer
- person
- family
- event
- place
- source
- citation
- media
- relationship/link tables (person_event, family_child, etc.)

## Fact Layer
- entity_fact: standardized tag/value pairs for complete coverage

## Enrichment Layer
- enrichment_result: derived outputs, versioned and confidence-scored

## Tag Registry
- gedcom_tag_definition: drives validation and standardization rules
