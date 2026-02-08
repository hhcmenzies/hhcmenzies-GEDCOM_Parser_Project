# Invariants

_Last updated: 2026-02-08_

These statements must always remain true. If a change violates an invariant, it must be treated as a breaking change and require an explicit contract update (and migration plan if data already exists).

## Identity
- All internal entities use stable, system-generated identifiers.
- External identifiers (e.g., GEDCOM xrefs) are never used as primary keys.
- Entity identifiers are immutable once assigned.

## GEDCOM Handling
- GEDCOM leveling architecture is preserved in raw storage.
- No GEDCOM tag is discarded.
- Unsupported or unknown tags are still captured and classified.
- Raw/original values are always preserved alongside any standardized/enriched forms.

## Standardization
- Standardized values are separate from raw values.
- Normalization never erases original meaning.
- Normalization rules must be deterministic: same input + same config => same standardized output.

## Enrichment
- Enrichment outputs are additive.
- Enrichment never overwrites standardized fields.
- Enrichment results declare dataset/version and confidence.
- Every enrichment is attributable (rule + source/dataset + version + run_id).

## Run Identity and Traceability
- Every run has a run_id.
- Every produced artifact and DB mutation can be traced back to a run_id.
- Config must be hashable/fingerprintable and recorded per run.

## Configuration
- Configuration is the single source of truth for toggles and dataset paths.
- Enrichment and normalization must be optional and parameter-driven (feature toggles).
- Missing datasets/config must fail clearly (no silent partial behavior).

## Data Sources / Datasets
- Dataset inputs must be versioned or checksummed (directly or via recorded provenance).
- Dataset semantics must be layerable: adding a dataset must not require rewriting the core pipeline.

## Storage Boundaries
- PostgreSQL is the authoritative relational store for ingested/normalized/enriched/audit state.
- Schema separation is preferred over separate databases unless a proven operational/security need exists.

## Outputs and Generated Artifacts
- Default runtime outputs go to `_runtime/` (ignored).
- Only intentionally versioned exports go under `_docs/_exports/` and must be explicitly staged.
- No generated output directories should be committed by accident.

## Repository Hygiene (Line Endings / Formatting)
- Text files committed to git must be normalized to LF.
- `.gitattributes` is authoritative for text/binary classification and line-ending normalization.
- A “renormalize” pass is acceptable when adopting or tightening `.gitattributes`.

## Documentation Authority
- `_docs/` is the only authoritative documentation tree.
- `/docs/` is deprecated/ignored; content must be migrated intentionally into `_docs/`.

## Graph Projection
- Neo4j nodes reference PostgreSQL identifiers.
- Neo4j state must match PostgreSQL state for the same ingestion run.
