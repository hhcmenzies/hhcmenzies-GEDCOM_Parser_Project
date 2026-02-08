# Project Scope

## Purpose
This project implements a comprehensive GEDCOM and DNA data ingestion,
processing, standardization, enrichment, and projection system.

The primary objectives are:
- To make sense of GEDCOM and DNA data by enforcing structure, semantics, and
  provenance.
- To normalize and standardize all supported data before enrichment.
- To support both analytical and visual exploration of genealogical relationships.

## Inputs
- GEDCOM files (primarily GEDCOM 5.5.5; others may be supported explicitly)
- DNA data files (vendor-specific raw files, CSVs, or similar)

Inputs may be processed singly or in bulk.

## Outputs
The system produces two first-class outputs:

1. PostgreSQL
   - Authoritative system of record
   - Lossless raw data capture
   - Canonical standardized entities
   - Enrichment outputs with provenance

2. Neo4j
   - Derived graph projection
   - Relationship traversal and visualization
   - Rebuildable at any time from PostgreSQL

## Non-Goals
- This system does not attempt to “fix” or silently correct genealogical errors.
- The system does not infer relationships without explicit provenance.
- Neo4j is not a system of record.
- Enrichment does not overwrite original or standardized values.

## Definition of Done (v1)
- Bulk GEDCOM ingestion is deterministic and idempotent.
- All GEDCOM tags are either:
  - explicitly modeled, or
  - captured as standardized facts.
- PostgreSQL fully represents standardized GEDCOM content.
- Neo4j accurately reflects PostgreSQL state.
