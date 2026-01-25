#!/usr/bin/env bash
set -euo pipefail

########################################
# GEDCOM PARSER FULL VERIFICATION SUITE (C.24.6)
########################################

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

INPUT="${INPUT:-$ROOT_DIR/mock_files/gedcom_1.ged}"
OUTDIR="${OUTDIR:-$ROOT_DIR/outputs}"

echo "=== GEDCOM PARSER FULL VERIFICATION SUITE (C.24.6) ==="
echo "Using input: $INPUT"
echo "Output directory: $OUTDIR"
echo

mkdir -p "$OUTDIR"

########################################
# [1] Run main parser → export.json
########################################
echo "[1] Running main parser → export.json"
python -m gedcom_parser.main \
  -i "$INPUT" \
  -o "$OUTDIR/export.json"

########################################
# [2] XREF/UUID resolver → export_xref.json
########################################
echo "[2] Running xref_resolver → export_xref.json"
python -m gedcom_parser.postprocess.xref_resolver \
  -i "$OUTDIR/export.json" \
  -o "$OUTDIR/export_xref.json"

########################################
# [3] Place standardization → export_standardized.json
########################################
echo "[3] Running place_standardizer → export_standardized.json"
python -m gedcom_parser.postprocess.place_standardizer \
  -i "$OUTDIR/export_xref.json" \
  -o "$OUTDIR/export_standardized.json"

########################################
# [4] Event disambiguation → export_events_resolved.json
########################################
echo "[4] Running event_disambiguator → export_events_resolved.json"
python -m gedcom_parser.postprocess.event_disambiguator \
  "$OUTDIR/export_standardized.json" \
  -o "$OUTDIR/export_events_resolved.json"

########################################
# [5] Name normalization → export_names_normalized.json
########################################
echo "[5] Running name_normalization → export_names_normalized.json"
python -m gedcom_parser.normalization.name_normalization \
  -i "$OUTDIR/export_events_resolved.json" \
  -o "$OUTDIR/export_names_normalized.json"

########################################
# [6] Media normalization (OBJE → first-class) → export_media_normalized.json
########################################
echo "[6] Running media_normalizer → export_media_normalized.json"
python -m gedcom_parser.postprocess.media_normalizer \
  -i "$OUTDIR/export_names_normalized.json" \
  -o "$OUTDIR/export_media_normalized.json"

########################################
# [7] Place registry promotion (C.24.5) → export_c24_5.json
########################################
echo "[7] Running place_registry_builder → export_c24_5.json"
python -m gedcom_parser.postprocess.place_registry_builder \
  -i "$OUTDIR/export_media_normalized.json" \
  -o "$OUTDIR/export_c24_5.json"

########################################
# [8] Place hierarchy build (C.24.6) → export_c24_6.json
########################################
echo "[8] Running place_hierarchy_builder → export_c24_6.json"
python -m gedcom_parser.postprocess.place_hierarchy_builder \
  -i "$OUTDIR/export_c24_5.json" \
  -o "$OUTDIR/export_c24_6.json"

########################################
# [9] Strict JSON Schema validation (C.24.6)
########################################
echo "[9] Validating export_c24_6.json against strict JSON Schema"

python - << 'PY'
import json
from jsonschema import Draft202012Validator

schema_path = "schemas/c24_6_canonical_export.strict.schema.json"
doc_path = "outputs/export_c24_6.json"

schema = json.load(open(schema_path, "r", encoding="utf-8"))
doc = json.load(open(doc_path, "r", encoding="utf-8"))

validator = Draft202012Validator(schema)
errors = sorted(validator.iter_errors(doc), key=lambda e: e.path)

if errors:
    print("[ERROR] Schema validation failed with", len(errors), "error(s). Showing first 25:")
    for e in errors[:25]:
        path = "$" + "".join(f"[{p!r}]" if isinstance(p, int) else f".{p}" for p in e.path)
        print("-", path, ":", e.message)
    raise SystemExit(1)

print("[OK] Schema validation passed")
PY

########################################
# [10] Cross-reference integrity checks (C.24.6)
########################################
echo "[10] Running cross-reference integrity checks (places/event linkage)"

python - << 'PY'
import json

doc = json.load(open("outputs/export_c24_6.json","r",encoding="utf-8"))
places = doc.get("places", {}) or {}

# 1) Every event.place_id must exist in root.places
missing = []
total_with_place_id = 0

for grp in ("individuals", "families"):
    for rec_ptr, rec in (doc.get(grp, {}) or {}).items():
        for idx, ev in enumerate(rec.get("events", []) or []):
            if not isinstance(ev, dict):
                continue
            pid = ev.get("place_id")
            if not pid:
                continue
            total_with_place_id += 1
            if pid not in places:
                missing.append((grp, rec_ptr, idx, pid))

if missing:
    print("[ERROR] Found events with place_id missing from root.places:", len(missing))
    for grp, rec_ptr, idx, pid in missing[:25]:
        print(f" - {grp}[{rec_ptr}].events[{idx}].place_id={pid!r} not in places")
    raise SystemExit(1)

# 2) If event.place_hierarchy exists, ensure it agrees with event.place_id
mismatch = []
total_with_h = 0

for grp in ("individuals", "families"):
    for rec_ptr, rec in (doc.get(grp, {}) or {}).items():
        for idx, ev in enumerate(rec.get("events", []) or []):
            if not isinstance(ev, dict):
                continue
            ph = ev.get("place_hierarchy")
            if not isinstance(ph, dict):
                continue
            total_with_h += 1
            pid = ev.get("place_id")
            if ph.get("place_id") and pid and ph["place_id"] != pid:
                mismatch.append((grp, rec_ptr, idx, pid, ph.get("place_id")))

if mismatch:
    print("[ERROR] Found event place_hierarchy.place_id mismatching event.place_id:", len(mismatch))
    for grp, rec_ptr, idx, pid, ph_pid in mismatch[:25]:
        print(f" - {grp}[{rec_ptr}].events[{idx}] place_id={pid!r} != place_hierarchy.place_id={ph_pid!r}")
    raise SystemExit(1)

print(f"[OK] Place linkage checks passed: events_with_place_id={total_with_place_id}, events_with_place_hierarchy={total_with_h}")
PY

########################################
# Final confirmation
########################################
echo
echo "=== C.24.6 VERIFICATION COMPLETE ==="
echo "Final canonical export:"
echo "  $OUTDIR/export_c24_6.json"
