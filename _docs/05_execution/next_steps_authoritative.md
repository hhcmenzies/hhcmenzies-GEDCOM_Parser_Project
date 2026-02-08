# Authoritative Next Steps (Project Direction)

These are the “do this next” items that drive the project forward and prevent drift.

## Next Steps
1. Lock the PostgreSQL place resolution schema.
2. Integrate GeoNames candidate generation with the canonical place tables.
3. Implement unresolved-place queries to support review workflows.
4. Defer UI and API expansion until data workflows are proven.

## Notes
- PostgreSQL remains system-of-record.
- Neo4j remains derived/projection (rebuildable).
- Standardization must precede enrichment.
