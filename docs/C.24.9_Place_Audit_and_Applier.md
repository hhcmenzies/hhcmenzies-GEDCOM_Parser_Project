p# C.24.9 — Place Audit, Plan, and Applier

## Status

**Phase:** C.24.9  
**Maturity:** Final (spec-level)  
**Depends on:** C.24.5, C.24.6, C.24.7, C.24.8  
**Introduces:** Auditable, deterministic, policy-driven application of place merge/split plans

---

## 1. Purpose

C.24.9 defines the **audit data model, invariants, and execution semantics** for applying place merge/split plans to a canonical GEDCOM export.

This phase bridges the gap between:

- **Verification** (C.24.8 — “is this safe?”)  
- **Mutation** (future C.25+ phases — “apply and persist changes”)

The C.24.9 applier is designed to be:

- Deterministic  
- Idempotent  
- Auditable  
- Policy-driven  
- Failure-safe  

No mutation may occur without an explicit, recorded justification.

---

## 2. Definitions

### 2.1 Identity Layers

| Layer | Description |
|------|------------|
| `place_id` | Stable canonical identity (C.24.5 / C.24.6) |
| `place_version_id` | Jurisdiction + temporal interpretation of a place (C.24.7) |
| `place_redirects` | Directed redirect graph mapping deprecated IDs to canonical IDs |
| `place_operations` | Append-only ledger of merge/split/supersede operations |

---

### 2.2 Plan vs Applied State

| Concept | Meaning |
|--------|--------|
| **Plan** | Declarative intent (`merge`, `split`, `supersede`) |
| **Applied** | Committed redirects + reference rewrites |
| **Dry-run** | Full evaluation without mutation |

Dry-run and apply modes must produce **identical reports**, differing only in the `committed` flag.

---

## 3. Core Applier Invariants

### 3.1 Determinism Invariants

1. Identical input + plan + policy → identical output  
2. All ordering must be explicit and stable  
3. No randomness, timestamps, or non-deterministic iteration  
4. If a “winner” is required and not specified, the applier must:
   - choose deterministically, **or**
   - fail with a hard error  

---

### 3.2 Idempotency Invariants

5. Re-applying the same plan must not:
   - add new redirects
   - duplicate ledger entries
   - re-rewrite references  
6. All rewrites must be safe to re-run  

---

### 3.3 Safety Invariants

7. **No partial commits**  
   Any hard error aborts the entire run  

8. **Redirect graph safety**
   - No self-redirects
   - No cycles
   - Chain depth ≤ configured maximum  

9. **Scope determinism**
   - No overlapping temporal scopes mapping to different targets
   - Exception only via explicit policy override  

10. **Jurisdiction compatibility**
    - Cross-jurisdiction merges are hard errors unless policy allows override  

11. **No silent data loss**
    - No deletions
    - Only additive redirects and reference rewrites  

---

### 3.4 Audit Invariants

12. Every applied operation **must be recorded** with:
    - operation id
    - kind
    - scope
    - outcome
    - severity counts
    - deterministic fingerprint  

13. Every rewritten reference must be **explainable**  

14. Dry-run and apply reports must be structurally identical  

---

### 3.5 Event-Level Invariants

15. `event.place_id` must remain meaningful  
16. `event.place_refs` must never contain dangling references  
17. Inferred or generated data must be explicitly labeled  

---

## 4. Severity Model

C.24.9 uses **policy-driven severity tiers**:

| Severity | Meaning |
|----------|--------|
| **Hard** | Abort run, no mutation |
| **Soft** | Allowed unless `fail_on_soft_warnings=true` |
| **Advisory** | Informational only |

Policy may control:
- failure thresholds
- allowed overrides
- maximum advisory counts  

---

## 5. Execution Model

The applier executes in **strict phases**.

---

### Phase 0 — Input & Policy Resolution

**Inputs**
- Canonical export (C.24.7)
- Optional place plan (C.24.9)
- Effective policy (defaults + overrides)

**Outputs**
- Resolved policy snapshot
- Run metadata (version, fingerprints, mode)

---

### Phase 1 — Schema Validation

- Validate export against **C.24.7 strict schema**
- Validate plan against **C.24.9 plan schema**

**Hard failure** on invalid structure.

---

### Phase 2 — Preflight Safety Verification

- Run C.24.8 verifier
- Ensure existing redirects are safe

**Hard failure** if foundation is unsafe.

---

### Phase 3 — Normalize Plan Operations

- Validate references
- Normalize scopes
- Resolve deterministic targets
- Classify operations:
  - candidate
  - blocked
  - rejected
  - advisory  

---

### Phase 4 — Redirect & Rewrite Simulation

- Compute redirect edges
- Compute event and reference rewrites
- Build patch plan  

No mutation occurs here.

---

### Phase 5 — Commit (Apply Mode Only)

If `apply`:
- Add redirects
- Append ledger entries
- Rewrite references
- Re-validate schema + safety  

If `dry-run`:
- Skip mutation  

---

### Phase 6 — Audit Report Emission

Report must include:
- severity counts
- applied / skipped / rejected operations
- redirect deltas
- rewrite counts
- deterministic fingerprints
- policy snapshot  

---

## 6. Diagnostic Verbosity

Applier must support verbosity levels:

| Level | Output |
|-------|--------|
| `quiet` | Summary only |
| `normal` | Per-operation outcomes |
| `verbose` | Sample affected records |
| `trace` | Rule-by-rule explanation |

---

## 7. Deferred but Explicitly Supported

C.24.9 does **not** require:
- probabilistic inference
- automatic split routing
- external gazetteers  

However, the applier must:
- detect insufficiency
- fail deterministically or emit advisory warnings  

---

## 8. Deliverables Introduced in C.24.9

- Audit data model
- Place plan schema
- Applier invariants
- Deterministic execution model  

---

## 9. Next Step

**Step 2:**  
Design the **C.24.9 applier module API**, including:

- function signatures
- inputs / outputs
- report object model
- CLI interface
- integration with `verify_all_C24_9.sh`
