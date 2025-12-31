# C.24.7 – Place Semantics (Temporal & Jurisdiction Layers)

## Status
**Final – Implemented and Verified**

This document defines the C.24.7 canonical extensions for interpreting places
across time and jurisdiction without altering GEDCOM’s single-PLAC semantics.

---

## 1. Purpose

C.24.7 introduces **semantic interpretations of places** while preserving:

- One GEDCOM `PLAC` per event
- One canonical `event.place_id` per event

C.24.7 **does not** introduce multiple physical places per event.

Instead, it provides:
- Temporal interpretations of a place
- Jurisdictional interpretations of a place
- Explicit metadata describing inferred or generated semantics

---

## 2. Core Principles

1. **Canonical Place Identity Is Stable**
   - `event.place_id` always refers to the C.24.5/6 canonical place

2. **Semantics Are Additive**
   - Temporal and jurisdictional meaning is layered on top
   - Nothing is deleted or restructured

3. **Deterministic and Idempotent**
   - Place version IDs are deterministic
   - Multiple runs produce identical output

4. **Configuration-Driven**
   - All C.24.7 features can be enabled/disabled via config or CLI

---

## 3. New Top-Level Registries

### 3.1 `jurisdiction_systems`

Defines legal, ecclesiastical, military, or other jurisdiction frameworks.

Example:
```json
"jurisdiction_systems": {
  "js:civil-us": {
    "id": "js:civil-us",
    "name": "United States Civil Jurisdiction",
    "generated": {
      "by": "place_version_builder",
      "rule": "ensure_default_jurisdiction_system",
      "inferred": true,
      "confidence": 0.9
    }
  }
}
