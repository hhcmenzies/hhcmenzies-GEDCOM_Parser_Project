# Constraints

## Data Authority
- PostgreSQL is the authoritative system of record.
- Neo4j is a derived projection and may be destroyed and rebuilt at any time.

## Processing Order
1. Parse
2. Sterilize
3. Standardize
4. Normalize
5. Enrich
6. Load / Project

No step may be skipped or reordered without explicit documentation.

## Idempotency
- Re-ingesting the same file with the same configuration must produce the same
  canonical results.
- Ingestion runs must be identifiable and auditable.

## Provenance
- Every stored fact must be traceable to its source:
  - file
  - GEDCOM xref
  - ingestion run
- Derived data must declare how it was produced.

## Safety
- Raw input is never destroyed.
- Invalid or malformed data is preserved with warnings.
- Enrichment must be reversible.

## Performance
- Bulk ingestion must be supported.
- Performance optimizations must not compromise correctness.
