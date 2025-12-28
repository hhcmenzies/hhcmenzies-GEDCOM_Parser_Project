# C.24.5 Canonical Export Schema

This document defines the **canonical JSON export** for phase **C.24.5** of the GEDCOM Parser pipeline.

The design is **additive and forward-compatible**:
- We never delete information from earlier stages.
- We promote frequently-used structures into first-class registries (OBJE already; **places** in C.24.5).
- We keep `raw` / extension buckets to preserve unknown GEDCOM vendor tags.

---

## Pipeline outputs (recommended)

C.24.5 is the first phase where the output should be considered *canonical* for downstream consumers.

Recommended staged outputs:

1. `outputs/export.json` – main parse + entity build
2. `outputs/export_xref.json` – UUID index + relationship resolution
3. `outputs/export_standardized.json` – events enriched with `standard_place`
4. `outputs/export_events_resolved.json` – event disambiguation/scoring (no structure loss)
5. `outputs/export_names_normalized.json` – adds `individual.name_block`
6. `outputs/export_media_normalized.json` – normalizes `media_objects.files[*]`
7. `outputs/export_c24_5.json` – **adds `places` registry + `event.place_id`**

---

## Top-level object

```jsonc
{
  "meta": { /* optional build info */ },
  "schema_version": "C.24.5",              // optional but recommended
  "individuals": { "<@I..@>": { ... } },
  "families":    { "<@F..@>": { ... } },
  "sources":     { "<@S..@>": { ... } },
  "repositories":{ "<@R..@>": { ... } },
  "media_objects":{ "<@M..@ or uuid>": { ... } },

  "places": { "<place_id>": { ... } },     // C.24.5+
  "uuid_index": { /* optional index */ }
}
```

### Registry keys
- `individuals`, `families`, `sources`, `repositories` are keyed by GEDCOM pointer where present.
- `media_objects` may be keyed by pointer OR UUID (when promoted from inline attachments).
- `places` is keyed by a deterministic `place_id` derived from `standard_place.id`.

---

## Individuals

Minimal required fields:
- `uuid` (deterministic)
- `pointer` (GEDCOM pointer, e.g. `@I123@`)

Recommended normalized fields:
- `names`: list of name dicts extracted from GEDCOM `NAME` blocks
- `name_block`: computed helper for convenience (C.24.5)

```jsonc
{
  "uuid": "…",
  "pointer": "@I123@",
  "gender": "M",
  "names": [ { "full": "John /Doe/", "given": "John", "surname": "Doe", ... } ],
  "name_block": {
    "primary": { ... },        // best display candidate
    "all": [ ... ],            // all name records
    "display": "John Doe",
    "normalized_display": "john doe"
  },
  "events": [ { ...Event... }, ... ],
  "families_as_spouse": ["@F1@"],
  "families_as_child": ["@F2@"],
  "notes": ["..."],
  "sources": ["@S1@"],
  "attachments": [ ... ],
  "attributes": [ ... ],
  "raw": { ... }
}
```

---

## Families

Minimal required fields:
- `uuid`
- `pointer`

```jsonc
{
  "uuid": "…",
  "pointer": "@F1@",
  "husband": "@I1@",
  "wife": "@I2@",
  "children": ["@I3@"],
  "events": [ { ...Event... } ],
  "attachments": [ ... ],
  "attributes": [ ... ],
  "raw": { ... }
}
```

---

## Events (canonical list form)

C.24.5 canonicalizes `events` as a **list** (not a tag→dict map).

Each event is a dict; unknown fields are permitted.

```jsonc
{
  "tag": "BIRT",
  "type": "Birth",
  "subtype": null,

  "date": {
    "raw": "19 Oct 1979",
    "normalized": "1979-10-19",
    "kind": "exact",
    "precision": "day"
  },

  "place": "Lawrence, Essex, Massachusetts, USA",
  "standard_place": {
    "id": "lawrence, essex, massachusetts, usa",
    "raw": "Lawrence, Essex, Massachusetts, USA",
    "normalized": "Lawrence, Essex, Massachusetts, USA"
  },

  "place_id": "lawrence, essex, massachusetts, usa",  // C.24.5+
  "notes": ["..."],
  "sources": ["@S123@"],
  "lineno": 39
}
```

### Place behavior in C.24.5
- `place` is preserved exactly (string or future object).
- `standard_place` is preserved exactly.
- `place_id` is **added** when `standard_place.id` exists.
- Downstream code should treat `place_id` as the canonical reference.

---

## Places registry (C.24.5)

A promoted de-duplicated place registry:

```jsonc
"places": {
  "lawrence, essex, massachusetts, usa": {
    "id": "lawrence, essex, massachusetts, usa",
    "normalized": "Lawrence, Essex, Massachusetts, USA",
    "raw_examples": [
      "Lawrence, Essex, Massachusetts, USA"
    ],
    "counts": {
      "events": 123,
      "individual_events": 120,
      "family_events": 3
    }
  }
}
```

### Promotion rules
- Built by scanning all individual + family events for `standard_place.id`.
- The record is updated additively:
  - adds `raw_examples` (limited sample list)
  - increments counts
- If later phases add structured parts/coordinates, those are preserved and the registry can be enriched without breaking consumers.

---

## Media objects (OBJE) as first-class entities

Media objects are already promoted in C.24.4.x and remain first-class in C.24.5.

A media object entry:

```jsonc
{
  "uuid": "…",
  "pointer": "@M123@",      // optional
  "title": "Photo",
  "files": [
    {
      "path": "photos/john_doe.jpg",
      "form": "jpg",
      "media_type": "photo",
      "title": null,
      "normalized": { /* added by media_normalizer */ }
    }
  ],
  "attributes": [ ... ],
  "raw": { ... }
}
```

Attachments from individuals/families may include pointers/IDs that relate back to `media_objects`.

---

## UUID index

`uuid_index` is optional and used as an interoperability accelerator:
- maps (record_type → pointer → uuid)
- allows fast resolution without re-walking registries

---

## Invariants (things we keep true)

- Registries are dicts keyed by stable identifiers.
- Unknown fields are always preserved under `raw` or allowed as additional properties.
- Normalizers do not delete; they only add or fill missing values.
- Idempotence: running any postprocess stage twice should not corrupt output.

---

## Files produced in this increment

- `place_registry_builder.py` (new)
- `c24_5_canonical_export.schema.json` (JSON Schema)
- `c24_5_canonical_export_openapi.yaml` (OpenAPI 3.1)
