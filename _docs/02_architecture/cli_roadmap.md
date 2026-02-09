# CLI Roadmap (Contract to Implementation)

_Last updated: 2026-02-09_

This document maps the current CLI surface to the target CLI contract in `execution_cli_contract.md`.
It defines what exists now, what is planned next, and how new commands should be introduced without breaking the stable surface.

## Current CLI (v0)
- gedcom doctor
- gedcom version
- gedcom stats <gedcom_path> [-v]
- gedcom export <gedcom_path> [--out/-o <path>] [--pretty] [-v]

## Target CLI (v1 contract)
From `_docs/02_architecture/execution_cli_contract.md`:

- gedcom run --input <path> --profile <name> [--config <yaml>] [--stages <list>]
- gedcom ingest --input <path> --run <run_id?> [--config <yaml>]
- gedcom normalize --run <run_id> [--config <yaml>]
- gedcom enrich --run <run_id> [--features <list>|--all] [--config <yaml>]
- gedcom validate --run <run_id> [--profile <name>] [--config <yaml>]
- gedcom export --run <run_id> --format gedcom|json|parquet|... [--out <dir>]
- gedcom audit tags --run <run_id> [--out <dir>]

## Introduction plan (non-breaking)
1) Keep current v0 commands as-is.
2) Add v1 pipeline commands as new commands (no rename of existing v0 commands yet).
3) When v1 export exists, keep v0 export as `export-file` (alias) or deprecate with a warning period.

## Next implementation targets
- Add command groups and empty shells (no pipeline execution yet):
  - run, ingest, normalize, enrich, validate, store, export-run
- Define config precedence and run_id generation contract.
