# C.24.8 — Place Merge / Split Semantics

**Status:** Draft (approved invariants)  
**Scope:** Defines canonical merge/split data model and verification rules for safe place consolidation and place identity evolution.  
**Depends on:** C.24.5 (places registry), C.24.6 (place hierarchy), C.24.7 (place versions + temporal/jurisdiction layers + event.place_refs)

---

## 1. Purpose

C.24.8 introduces a **safe, reversible, auditable** model for place identity changes:

- **Merge:** Consolidate multiple place versions (and/or their underlying place identities) into a single canonical identity.
- **Split:** Represent divergence where a single identity should be separated into multiple identities.

This phase does **not** require destructive edits to historical data. All operations are **additive**, with explicit provenance and reversibility.

---

## 2. Terminology

### 2.1 Place vs Place Version

- `places[place_id]` (C.24.5/6) represents a canonical place identity and its hierarchy.
- `place_versions[pv_id]` (C.24.7) represents a place interpretation in a **jurisdiction system** and **temporal bucket** (currently year-based).

### 2.2 Events

- `event.place_id` remains the canonical anchor (C.24.5/6).
- `event.place_refs[]` (C.24.7) contains interpretations of `event.place_id` into `place_version_id` (+ temporal + jurisdiction).

---

## 3. Canonical Invariants (Merge/Split Safety)

These invariants drive verifier behavior and schema expectations.

### 3.1 Hard Safety Invariants (merge forbidden)

**H1 — Temporal Non-Overlap Invariant**  
Two `place_version` records must not be merged if their temporal windows do not overlap AND neither is open-ended.

**H2 — Jurisdiction System Isolation**  
No auto-merge across different `jurisdiction_system_id`.  
Manual override is permitted, but must be explicitly recorded.

**H3 — Hierarchy Root Conflict**  
Do not merge if the *top-level root ancestor* differs (derived from `places[place_id].ancestor_ids`), unless explicitly overridden with audit trail.

**H4 — Place Identity Immutability / Non-Destructive**  
Merges must not delete or rewrite original IDs. They must be represented as additive records.

---

### 3.2 Soft Conflict Invariants (allowed with warnings)

**S1 — Partial Temporal Overlap**  
Overlapping but non-identical windows are allowed, but should reduce confidence.

**S2 — Hierarchy Depth Mismatch**  
Merging different granularity levels is suspicious (often containment, not identity).

**S3 — Sparse Evidence**  
Low event support (few linked events) reduces confidence and should be flagged.

---

### 3.3 Override-Only Invariants (manual authority required)

**O1 — Name Normalization Divergence**  
If normalized place labels diverge beyond trivial formatting/diacritics, require manual override.

**O2 — Non-Civil Jurisdiction Overlay**  
Civil vs ecclesiastical vs military overlays require explicit cross-system mapping records + override.

---

### 3.4 Split Detection Invariants (signals that split is needed)

**D1 — Temporal Fork**  
Same identity used across clearly distinct eras suggests split.

**D2 — Jurisdiction Transition Without Versioning**  
Boundary shifts without corresponding version separation suggests split.

---

### 3.5 Metadata Preservation Invariants (always enforced)

**M1 — Event Referential Integrity**  
No event loses its `place_id` or `place_refs`.

**M2 — Provenance & Auditability**  
All merge/split records include rule(s), confidence, timestamp, and actor.

**M3 — Reversibility**  
All merges and splits are reversible (no destructive changes to original records).

---

## 4. Canonical Data Model (C.24.8 Additive Records)

C.24.8 introduces a top-level registry:

- `place_change_sets` (recommended)
- or directly: `place_merges` and `place_splits`

### 4.1 Recommended: `place_change_sets`

```json
{
  "place_change_sets": {
    "pcs_2025-01-01T12:00:00Z_abcd1234": {
      "id": "pcs_2025-01-01T12:00:00Z_abcd1234",
      "kind": "merge" | "split",
      "actor": "system" | "human:<id>",
      "timestamp": "2025-01-01T12:00:00Z",
      "confidence": 0.0,
      "rules": ["H2", "S1"],
      "override": false,
      "notes": "Free text reason",
      "payload": { ... } 
    }
  }
}
