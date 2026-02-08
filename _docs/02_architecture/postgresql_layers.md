# PostgreSQL Data Layers

## Overview
PostgreSQL stores four layers:
- Raw (lossless)
- Canonical (standardized entities)
- Facts (complete tag coverage)
- Enrichment (derived outputs)

This prevents loss of GEDCOM detail while allowing the canonical schema to evolve safely.

---

## Raw Layer (Lossless GEDCOM Capture)

### Goals
- Preserve GEDCOM leveling architecture exactly.
- Preserve all tags and child tag structures.
- Preserve raw value strings and pointers.
- Store parse warnings without discarding records.

### Core Concepts
- Each GEDCOM line becomes a node.
- Node fields include:
  - level
  - tag
  - value_raw
  - xref_id_raw (e.g., @I1@)
  - pointer_xref_raw (if value is a pointer)
  - parent_node_id (tree structure)

### Minimum Raw Tables (Conceptual)
- ingestion_run
- ingested_file
- gedcom_raw_node
- (optional) gedcom_raw_line
- run_issue

### Invariants (Raw)
- No GEDCOM tag is discarded.
- Parent-child relationships reflect leveling.
- Warnings are stored; raw content remains intact.

---

## Canonical Layer (Standardized Entities)

### Goals
- Provide queryable, normalized entities.
- Enforce referential integrity.
- Store standardized values separately from raw values.

### Canonical Entities (v1)
- person
- family
- event
- place
- source
- citation
- media

### Invariants (Canonical)
- Stable internal IDs.
- Raw GEDCOM xrefs retained as provenance fields.
- No enrichment overwrites canonical standardized fields.

---

## Fact Layer (Complete Tag Coverage)

### Goal
Guarantee: “every GEDCOM tag and child tag is represented,” even if not mapped to canonical columns yet.

### Concept
- entity_fact stores standardized tag/value pairs with provenance.
- Used for:
  - custom tags
  - obscure standard tags not modeled yet
  - interim coverage during development

### Invariants (Facts)
- A standardized representation exists for any tag we parse.
- Facts link back to raw nodes and canonical entities when possible.

---

## Enrichment Layer (Additive)

### Goals
- Store derived interpretations and enhancements.
- Version and fingerprint all enrichment steps.
- Make enrichment repeatable and reversible.

### Examples
- name variants, phonetics, romanization
- date normalization and uncertainty ranges
- place parsing and later geocoding candidates
- relationship confidence annotations (never silent)

### Invariants (Enrichment)
- Additive only.
- Versioned and confidence-scored.
- Contains provenance and input fingerprinting.
