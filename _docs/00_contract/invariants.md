# Invariants

These statements must always remain true.

## Identity
- All internal entities use stable, system-generated identifiers.
- External identifiers (e.g., GEDCOM xrefs) are never used as primary keys.

## GEDCOM Handling
- GEDCOM leveling architecture is preserved in raw storage.
- No GEDCOM tag is discarded.
- Unsupported or unknown tags are still captured and classified.

## Standardization
- Standardized values are separate from raw values.
- Normalization never erases original meaning.

## Enrichment
- Enrichment outputs are additive.
- Enrichment never overwrites standardized fields.
- Enrichment results declare version and confidence.

## Graph Projection
- Neo4j nodes reference PostgreSQL identifiers.
- Neo4j state must match PostgreSQL state for the same ingestion run.
