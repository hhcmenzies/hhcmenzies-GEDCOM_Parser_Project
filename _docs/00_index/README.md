# Documentation Index (Authoritative)

This `_docs/` tree is the **only authoritative documentation** for this project.

## Start Here (End-User Entry Point)
## Project Contract (Must Read)
- `_docs/00_contract/PROJECT_CONTRACT.md` — binding definition of scope, principles, execution model, and non-goals

All documentation, code, pipelines, and enrichment behavior must conform to this contract.

- `_docs/03_state/RUNBOOK.md` — primary end-user runbook and system overview

## Documentation Map
- `_docs/00_contract/` — project contracts: scope, non-goals, standards, definitions
- `_docs/00_index/` — navigation, tables of contents, link maps
- `_docs/01_environment/` — setup: OS, Python, PyCharm, PostgreSQL, Neo4j, tooling
- `_docs/02_architecture/` — system design: pipelines, modules, schemas, APIs, UI plan
- `_docs/03_state/` — current status, active work, repo working state, runbook
- `_docs/04_history/` — decisions, rationale, ADRs, migration notes
- `_docs/05_execution/` — operational procedures: runs, commands, checklists
- `_docs/06_handoff/` — AI and human handoff packs, prompt templates, context bundles
- `_docs/_exports/` — generated exports (only if intentionally versioned)

## Rules
1. Anything important must live in `_docs/` (not `/docs/`).
2. Only `_docs/` should be referenced as authoritative in issues, PRs, and commits.
3. Add new docs by category and link them here.

## Next Docs to Promote (Tracked Soon)
- `_docs/03_state/current_status.md`
- `_docs/03_state/repo_working_state.md`
- `_docs/03_state/active_work.md`
