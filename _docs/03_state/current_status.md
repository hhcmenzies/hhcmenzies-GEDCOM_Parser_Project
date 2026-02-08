# Current Project Status

_Last updated: 2026-02-08_

## Repository State
- Default branch: `main`
- Working tree: clean
- Documentation system: `_docs/` is authoritative
- Legacy `/docs/` directory: ignored and deprecated

## Implemented and Committed
- GEDCOM test fixtures under `tests/fixtures/gedcom/`
- `.gitattributes` enforcing LF and binary handling
- PostgreSQL schema and pipeline SQL scripts under `db/sql/`
- Initial Python pipeline modules:
  - `src/extract_places.py`
  - `src/generate_candidates.py`
  - `src/load_places_csv.py`
- RUNBOOK skeleton established

## Database State
- PostgreSQL database: `gedcom`
- GeoNames currently integrated as primary geolocation dataset
- Schema and ingestion scripts tracked but not yet fully documented

## Not Yet Formalized
- CLI interface definition
- Name (NAME) tokenization and enrichment rules
- Full GEDCOM tag normalization matrix
- API surface (internal or external)
- Neo4j integration
- TIGER / secondary geospatial layers
- Validation and QA pipelines

## Known Constraints
- GEDCOM exporters vary (FTM vs Ancestry)
- NAME child tags often missing or collapsed
- Place strings are historically inconsistent
- Enrichment must be optional and parameter-driven

## Immediate Next Step
- Formalize execution model and pipeline stages
