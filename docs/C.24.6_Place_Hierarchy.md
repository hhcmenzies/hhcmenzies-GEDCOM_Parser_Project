# C.24.6 – Place Hierarchy

This document defines how **places** evolve from the flat `standard_place` strings introduced in C.24.4/24.5 into a first-class **hierarchical** registry (C.24.6+), while preserving backward compatibility.

## Current (C.24.5) behavior

- `place_standardizer` adds `event.standard_place`:
  - `{ id, raw, normalized }`
- `place_registry_builder` promotes a top-level `places` registry:
  - `root.places[place_id] = PlaceRecord`
  - `event.place_id = place_id`

This gives:
- **deduplication** (many events → one place record)
- a stable identifier for later enrichment

## C.24.6 goal

Extend `PlaceRecord` so places can be represented as a **tree/graph**:

- Country → State/Province → County → City → Locality
- Support multiple naming variants, historical names, and geopolitical changes
- Allow geocoding and coordinate enrichment without mutating events

## Canonical identifiers

### `place_id` (stable)
Continue using the C.24.5 `standard_place.id` as the *stable key* for registry membership.

- Default: lowercased normalized place string.
- If you introduce a richer canonicalization later, preserve the original id under `aliases`.

### `place_node_id` (optional future)
If the same `place_id` needs multiple interpretations (rare, but possible for ambiguous strings), introduce a secondary identifier:

- `place_node_id = "<place_id>#<hash>"`

Events continue to reference `place_id` unless ambiguity forces an opt-in.

## Proposed PlaceRecord v2 shape (C.24.6)

```json
{
  "id": "lawrence, essex, massachusetts, usa",
  "normalized": "Lawrence, Essex, Massachusetts, USA",
  "raw_examples": ["Lawrence, Essex, Massachusetts, USA"],

  "hierarchy": {
    "level": "city",
    "parts": {
      "locality": null,
      "city": "Lawrence",
      "county": "Essex",
      "state": "Massachusetts",
      "country": "USA"
    },
    "parent_id": "essex, massachusetts, usa",
    "ancestors": [
      "usa",
      "massachusetts, usa",
      "essex, massachusetts, usa"
    ]
  },

  "geo": {
    "coordinates": { "lat": 42.707, "lon": -71.163 },
    "geohash": "drt2....",
    "source": "geocoder:xyz",
    "confidence": 0.83
  },

  "names": {
    "preferred": "Lawrence, Essex, Massachusetts, USA",
    "variants": ["Lawrence, Massachusetts, USA"],
    "historical": []
  },

  "counts": { "events": 123, "individual_events": 100, "family_events": 23 },

  "raw": { "vendor": "..." }
}
```

### Notes
- All new blocks are **additive**.
- Do **not** remove `raw_examples` or `counts` because they are useful for debugging and analytics.
- `hierarchy.parent_id` should reference another record in `root.places`.

## How hierarchy is built

### 1) Parse into parts
A conservative parser should attempt to split normalized strings into parts using:
- comma separation
- known abbreviations (e.g., US states)
- GEDCOM producer quirks (extra commas, double spaces)

Keep the original string if parsing fails.

### 2) Determine level
The *deepest non-empty* part implies the node level:
- If `city` exists → level is `city`
- If only `state` and `country` exist → level is `state`

### 3) Create parent nodes
For each node, create or reuse parents:
- `Lawrence, Essex, Massachusetts, USA` parent is `Essex, Massachusetts, USA`
- Parent’s parent is `Massachusetts, USA`
- Root is `USA`

### 4) Record ancestry
`ancestors` is a convenience list for queries and indexing.

## Event linkage rules (C.24.6+)

- `event.place_id` remains required when `event.standard_place` exists.
- Optional enrichment:
  - `event.place_node_id` (only if needed)
  - `event.geo` (should be avoided; prefer registry-level geo)

## Suggested implementation plan

1. Keep current `place_registry_builder` unchanged (C.24.5).
2. Add `place_hierarchy_builder.py` (C.24.6):
   - reads `root.places`
   - adds/updates `hierarchy` + parent nodes
   - idempotent and additive
3. Add optional `place_geocoder.py` as a separate, opt-in stage.

## Validation expectations

In strict schema mode (C.24.5), `places[*].counts` and `event.place_id` should be consistent:

- `len(root.places) >= 1` when any events have `standard_place`
- `events_with_standard_place == events_with_place_id`
