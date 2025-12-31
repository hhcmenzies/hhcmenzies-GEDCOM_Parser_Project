# C.24.7 — Place Semantics (Temporal & Jurisdiction Layers)

**Status:** FINAL  
**Canonical Level:** C.24.7  
**Applies To:** GEDCOM canonical export JSON  
**Prerequisites:** C.24.5 (Place Registry), C.24.6 (Place Hierarchy)

---

## 1. Purpose and Scope

C.24.7 introduces **temporal and jurisdictional semantics** for places without altering the physical interpretation of GEDCOM `PLAC` data.

This phase answers:

> **“What did this place mean, under which jurisdiction, at what time?”**

C.24.7 does **not** introduce:

- Place merging or splitting  
- Historical boundary mutation  
- Retrospective rewriting of events  

Those are explicitly deferred to **C.24.8+**.

---

## 2. Core Principles

### 2.1 Single Physical Place per Event

Each GEDCOM event continues to represent **one physical place**, expressed canonically via:

- `event.place_id`

This value:

- Originates from normalized GEDCOM `PLAC`  
- Refers to a single canonical place in `root.places`  
- Is **never duplicated or replaced**

### 2.2 Interpretations, Not Replacements

C.24.7 introduces **interpretations of a place**, not new places.

These interpretations are modeled as:

- **Place versions** (`root.place_versions`)  
- **Event place references** (`event.place_refs`)  

---

## 3. New Canonical Structures

### 3.1 Jurisdiction Systems

#### Purpose
A jurisdiction system defines **which legal, administrative, or institutional authority** is being referenced.

#### Location
- `root.jurisdiction_systems`

#### Minimal Record Shape

```json
{
  "id": "js:civil-us",
  "name": "United States Civil Jurisdiction",
  "generated": {
    "by": "place_version_builder",
    "rule": "ensure_default_jurisdiction_system",
    "inferred": true,
    "enrichment_candidate": false,
    "confidence": 0.9
  }
}
```

#### Notes

- Jurisdiction systems are **global**.  
- At least one default system **MUST** exist.  
- Systems may be user-defined or inferred.

---

### 3.2 Place Versions

#### Definition
A **place version** is a *time-bound, jurisdiction-scoped interpretation* of a canonical place.

#### Location
- `root.place_versions`

#### Identity Rule
A place version is uniquely defined by:

- `(place_id, jurisdiction_system_id, temporal bucket)`

#### Minimal Record Shape

```json
{
  "id": "pv_<sha1>",
  "place_id": "paris, île-de-france, france",
  "jurisdiction_system_id": "js:civil-fr",
  "temporal": {
    "bucket": "year",
    "year": 1789
  },
  "generated": { "..." : "..." },
  "meta": {
    "events": 12,
    "individual_events": 8,
    "family_events": 4
  }
}
```

#### Determinism

- IDs are deterministic.  
- Re-running the pipeline produces identical IDs.  
- Insertion order does not affect identity.

---

## 4. Temporal Semantics

### 4.1 Temporal Buckets

C.24.7 supports **year-based temporal buckets only**.

```json
"temporal": {
  "bucket": "year",
  "year": 1912
}
```

If no year can be determined:

```json
"temporal": {
  "bucket": "year",
  "open_ended": true
}
```

### 4.2 Year Extraction Rules

Years are extracted conservatively from:

- `event.date.normalized`  
- `event.date.raw`  
- ISO-like date strings  
- fallback string scanning (last resort)

If no reliable year is found:

- `open_ended` is used **if enabled**  
- the inference is flagged (see §7)

---

## 5. Event Place References (`event.place_refs`)

### 5.1 Purpose

`event.place_refs` links an event to **one or more place versions**.

It expresses:

> **“This event’s place, interpreted under this jurisdiction, at this time.”**

### 5.2 Structure

```json
{
  "place_id": "paris, île-de-france, france",
  "place_version_id": "pv_abc123",
  "jurisdiction_system_id": "js:civil-fr",
  "temporal": {
    "bucket": "year",
    "year": 1789
  },
  "generated": { "..." : "..." }
}
```

### 5.3 Multiplicity Rules

By default:

- **one** place reference per event  
- multiple references are **disabled**

Multiple references MAY be enabled via configuration but:

- they **do not** represent multiple physical places  
- they represent **parallel interpretations**

Example valid use cases:

- civil vs ecclesiastical jurisdiction  
- colonial vs post-independence governance  

---

## 6. Configuration Semantics

All C.24.7 behavior is configurable via:

```yaml
place_processing:
  enable_place_versions: true
  enable_event_place_refs: true
  allow_multiple_place_refs_per_event: false
  default_jurisdiction_system: js:civil-us
  jurisdiction_systems_enabled:
    - js:civil-us
  temporal:
    bucket: year
    open_ended_fallback: true
```

---

## 7. Generated vs Inferred Metadata

Any automatically created structure may include:

```json
"generated": {
  "by": "place_version_builder",
  "rule": "year_from_event_date",
  "inferred": false,
  "enrichment_candidate": false,
  "confidence": 0.95
}
```

### Interpretation

| Field | Meaning |
|---|---|
| `inferred` | Derived indirectly |
| `enrichment_candidate` | Worth future enhancement |
| `confidence` | Heuristic certainty |

---

## 8. Invariants and Guarantees

C.24.7 guarantees:

- No mutation of `event.place_id`  
- No deletion of existing place records  
- Idempotent execution  
- Schema-valid output  
- Forward compatibility with merge/split semantics  

---

## 9. Explicit Non-Goals

C.24.7 does **not**:

- Merge places  
- Split places  
- Rewrite historical truth  
- Resolve boundary disputes  
- Modify event meaning  

These are deferred to **C.24.8+**.

---

## 10. Forward Compatibility

C.24.7 is designed to support:

- Place merges & splits (C.24.8)  
- Temporal validity windows  
- Jurisdiction overlays  
- Provenance and confidence propagation  
- Semantic querying  

---

## 11. Summary

C.24.7 establishes **semantic stability** between:

- Physical place identity  
- Jurisdictional interpretation  
- Temporal context  

It is the **foundation** upon which historical reasoning is safely built.

---

**End of C.24.7 — Place Semantics**
