# Active Work

_Last updated: 2026-02-08_

## Current Focus
- Formalizing end-to-end system design for GEDCOM normalization and enrichment
- Establishing authoritative documentation structure
- Defining execution model before expanding code

## In Progress
- RUNBOOK expansion (system design, pipelines, CLI)
- Documentation index and state tracking
- Clarifying NAME and PLAC enrichment rules

## Blocked / Waiting
- None

## Next Decisions Needed
- Execution pipeline stages (ingest → normalize → enrich → validate → store → export)
- CLI command surface
- Database schema boundaries (schemas vs databases)
- Canonical GEDCOM tag normalization matrix

## Explicitly Not Doing Yet
- Neo4j implementation
- UI / API implementation
- TIGER ingestion
- DNA modeling

## Notes
- All enrichment must be parameter-driven and optional
- Provenance and traceability are mandatory design constraints
