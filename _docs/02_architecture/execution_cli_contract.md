# Execution & CLI Contract

_Last updated: 2026-02-08_

## 1) Canonical Execution Model (Stages)
The system is a staged pipeline. Each stage must be callable independently and composable into end-to-end runs.

Stages (logical order):
1. ingest      : read GEDCOM; persist raw + parsed structures
2. normalize   : enforce structural standards (including creating defined child tags)
3. enrich      : dataset-driven enhancements (names, places, occupations, etc.)
4. validate    : QA checks, audits, constraints, cross-field consistency
5. store       : write authoritative records to PostgreSQL (and later project to Neo4j)
6. export      : produce GEDCOM + reports + API/UI-ready views

All stages must support:
- deterministic outputs: same inputs + same config → same results
- provenance: rule + dataset + version + run_id for every enrichment
- optionality: stage/feature toggles; ability to run only selected stages

## 2) Run Identity and Traceability
Every invocation creates a run_id.
Minimum run metadata:
- run_id (uuid or timestamp+uuid)
- started_at, finished_at
- git_commit (optional but recommended)
- config_fingerprint (hash of normalized config)
- input_manifest (files, checksums)
- output_manifest (artifacts, checksums)

## 3) CLI Contract (Stable Surface)
Primary entrypoint:
- `gedcom` (console script)

### 3.1 Global conventions
- Commands must be idempotent where possible.
- Default outputs go to `_runtime/` (ignored) unless explicitly directed.
- Any output intended to be versioned must go to `_docs/_exports/` and be explicitly staged.

### 3.2 Commands (v1 target)
A. Project / environment
- `gedcom doctor`              : validate environment, dependencies, DB connectivity
- `gedcom version`             : show app + schema versions + git commit

B. Ingest / normalize / enrich / validate / export
- `gedcom ingest   --input <path> --run <run_id?> [--config <yaml>]`
- `gedcom normalize --run <run_id> [--config <yaml>]`
- `gedcom enrich   --run <run_id> [--features <list>|--all] [--config <yaml>]`
- `gedcom validate --run <run_id> [--profile <name>] [--config <yaml>]`
- `gedcom export   --run <run_id> --format gedcom|json|parquet|... [--out <dir>]`

C. One-shot end-to-end
- `gedcom run --input <path> --profile <name> [--config <yaml>] [--stages <list>]`

D. Specialized (initial focus)
- `gedcom names parse --input <path> [--config <yaml>]`         : NAME tokenization test mode
- `gedcom places resolve --run <run_id> [--config <yaml>]`      : GeoNames resolution pipeline
- `gedcom audit tags --run <run_id> [--out <dir>]`              : tag audits & summaries

## 4) Configuration Contract (YAML-first)
Single “top-level” config file, with profiles overlaying defaults.

### 4.1 Required sections (v1)
- `project`: paths, runtime dirs, logging
- `input`: GEDCOM input options (encoding, permissive parsing)
- `stages`: stage toggles and order constraints
- `features`: enrichment toggles (names, places, occupations, notes mining)
- `datasets`: dataset paths + versions (prefixes, military ranks, GeoNames, TIGER later)
- `db`: PostgreSQL connection + schema mapping
- `qa`: validation profiles, thresholds, report outputs
- `export`: formats, output paths, redaction options

### 4.2 Config principles
- Every feature has:
  - enabled/disabled
  - parameters
  - provenance requirements
  - confidence scoring strategy (even if coarse)
- All config must be hashable and logged per run_id.

## 5) PostgreSQL Boundary Rule (DB vs Schemas)
Default: one database `gedcom` with multiple schemas.
Recommended schema split:
- `core`       : ingested + normalized GEDCOM entities
- `enrich`     : enrichment outputs + attribution
- `geonames`   : reference tables/functions for GeoNames
- `tiger`      : future TIGER layers
- `audit`      : QA, validation results, run metadata

Do not split into multiple databases unless:
- scale/performance requires it
- security boundaries require it
- operational separation is proven necessary

## 6) Definition of Done (for adding a new stage/feature)
A stage/feature is “done” only when:
- documented here + in RUNBOOK
- has CLI entrypoint and help text
- has config section defined
- writes provenance + run metadata
- has at least one fixture test
