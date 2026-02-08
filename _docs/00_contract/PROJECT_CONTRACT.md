# Project Contract — GEDCOM Parser & Enrichment System

_Last updated: 2026-02-08_

## 1. Mission (What this project is)
This project ingests GEDCOM files and produces a standardized, normalized, and enriched representation of genealogical data for:
- consistency across exporters (e.g., FTM vs Ancestry),
- high-quality downstream use (database, APIs, UI),
- optional enrichment from curated datasets (names, military titles, geography, etc.),
- provenance and traceability for every change.

## 2. Primary Objectives (What we will accomplish)
1. Normalize and enrich GEDCOM tags while preserving original meaning.
2. Promote collapsed/implicit values into explicit child tags (where applicable).
3. Standardize NAME parsing into structured components (e.g., GIVN, SURN, NPFX, NSFX, TITL or equivalent).
4. Standardize PLAC and MAP/LATI/LONG via geolocation datasets (GeoNames first; TIGER later).
5. Provide repeatable pipelines with clear configuration, validation, and auditable outputs.
6. Support end-user usage via CLI first, then APIs/UI.

## 3. Non-Goals (What we will NOT do yet)
- Build Neo4j integration until the PostgreSQL pipeline and schema are stable.
- Build web UI/UX or public APIs until CLI and database contracts are stable.
- Implement TIGER ingestion until GeoNames + place pipeline are stable.
- Implement DNA modeling until GEDCOM normalization/enrichment contracts are stable.

## 4. Core Principles
- Optionality: enrichment is parameter-driven and can be enabled/disabled by feature.
- Determinism: same inputs + same config = same outputs.
- Traceability: every enrichment and normalization must be attributable (rule + source + timestamp/run id).
- Preservation: never lose original values; store raw + normalized + enriched forms.
- Layering: GeoNames is one layer; other datasets can be added without rewriting the core.

## 5. Authoritative Documentation Rules
- `_docs/` is the only authoritative documentation tree.
- `/docs/` is deprecated and ignored; content must be migrated intentionally into `_docs/`.
- RUNBOOK is the primary end-user entry point:
  - `_docs/03_state/RUNBOOK.md`

## 6. Canonical Execution Model (Pipeline stages)
The system is organized into stages that can be invoked independently:
1. Ingest: read GEDCOM, parse records, persist raw/structured forms.
2. Normalize: standardize tag structures (including creating missing child tags where defined).
3. Enrich: apply dataset-based improvements (names, places, occupations, etc.).
4. Validate: run QA checks, schema constraints, and rule audits.
5. Store: persist to PostgreSQL (and later Neo4j) with provenance.
6. Export: write GEDCOM and/or API-ready forms.

## 7. Naming and Tag Enrichment Contract (High-level)
- The system may create explicit child tags from an existing parent value when rules support it.
- Example: parse `NAME` into child tags based on tokenization rules and datasets.
- Any inferred value must:
  - carry a confidence score (even if coarse),
  - record its provenance (rule + dataset + run id),
  - allow reversion or disablement by config.

## 8. Database Contract (High-level)
- PostgreSQL is the authoritative relational store for ingestion, normalization, enrichment, and audits.
- GeoNames is integrated as a reference dataset for place resolution.
- “Schema vs database” rule:
  - Default: one database (`gedcom`) with multiple schemas unless separation is required by scale/security.
  - Layers (e.g., geonames, tiger, gedcom_core) should be schemas, not separate DBs, unless proven necessary.

## 9. Definition of Done (for planned work)
A feature or pipeline stage is “done” when:
- documented in RUNBOOK,
- has a defined CLI or callable interface,
- has configuration parameters documented,
- produces auditable outputs (logs/reports),
- has at least one fixture/test case.

