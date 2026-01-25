#!/usr/bin/env bash
set -euo pipefail

########################################
# GEDCOM PARSER FULL VERIFICATION SUITE (C.24.7)
########################################

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

INPUT="${INPUT:-$ROOT_DIR/mock_files/gedcom_1.ged}"
OUTDIR="${OUTDIR:-$ROOT_DIR/outputs}"
CONFIG="${CONFIG:-$ROOT_DIR/config/gedcom_parser.yml}"

echo "=== GEDCOM PARSER FULL VERIFICATION SUITE (C.24.7) ==="
echo "Using input: $INPUT"
echo "Output directory: $OUTDIR"
echo "Config: $CONFIG"
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
# [9] Place versioning + event.place_refs (C.24.7) → export_c24_7.json
########################################
echo "[9] Running place_version_builder → export_c24_7.json"
python -m gedcom_parser.postprocess.place_version_builder \
  -i "$OUTDIR/export_c24_6.json" \
  -o "$OUTDIR/export_c24_7.json" \
  --config "$CONFIG"

########################################
# [10] Strict JSON Schema validation (C.24.7)
########################################
echo "[10] Validating export_c24_7.json against strict JSON Schema"

python - << 'PY'
import json
from jsonschema import Draft202012Validator

schema_path = "schemas/c24_7_canonical_export.strict.schema.json"
doc_path = "outputs/export_c24_7.json"

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
# [11] Cross-reference integrity checks (C.24.7)
########################################
echo "[11] Running cross-reference integrity checks (places/place_versions/place_refs)"

python - << 'PY'
import json

doc = json.load(open("outputs/export_c24_7.json","r",encoding="utf-8"))
places = doc.get("places", {}) or {}
place_versions = doc.get("place_versions", {}) or {}
jurisdictions = doc.get("jurisdiction_systems", {}) or {}

# -------------------------------------------------------------------
# A) Every event.place_id must exist in root.places
# -------------------------------------------------------------------
missing_place = []
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
                missing_place.append((grp, rec_ptr, idx, pid))

if missing_place:
    print("[ERROR] Found events with place_id missing from root.places:", len(missing_place))
    for grp, rec_ptr, idx, pid in missing_place[:25]:
        print(f" - {grp}[{rec_ptr}].events[{idx}].place_id={pid!r} not in places")
    raise SystemExit(1)

# -------------------------------------------------------------------
# B) place_versions integrity: place_id exists and js exists
# -------------------------------------------------------------------
pv_missing_place = []
pv_missing_js = []
for pv_id, pv in (place_versions or {}).items():
    if not isinstance(pv, dict):
        continue
    pid = pv.get("place_id")
    js = pv.get("jurisdiction_system_id")
    if pid and pid not in places:
        pv_missing_place.append((pv_id, pid))
    if js and js not in jurisdictions:
        pv_missing_js.append((pv_id, js))

if pv_missing_place:
    print("[ERROR] place_versions contain place_id not in root.places:", len(pv_missing_place))
    for pv_id, pid in pv_missing_place[:25]:
        print(f" - place_versions[{pv_id}].place_id={pid!r} not in places")
    raise SystemExit(1)

if pv_missing_js:
    print("[ERROR] place_versions contain jurisdiction_system_id not in root.jurisdiction_systems:", len(pv_missing_js))
    for pv_id, js in pv_missing_js[:25]:
        print(f" - place_versions[{pv_id}].jurisdiction_system_id={js!r} not in jurisdiction_systems")
    raise SystemExit(1)

# -------------------------------------------------------------------
# C) event.place_refs integrity:
#    - place_version_id exists
#    - jurisdiction_system_id exists
#    - place_id matches event.place_id unless explicitly different (future)
#    - temporal sanity (year bucket)
# -------------------------------------------------------------------
refs_total = 0
refs_bad_pv = []
refs_bad_js = []
refs_bad_place = []
refs_bad_temporal = []

for grp in ("individuals", "families"):
    for rec_ptr, rec in (doc.get(grp, {}) or {}).items():
        for idx, ev in enumerate(rec.get("events", []) or []):
            if not isinstance(ev, dict):
                continue
            pid = ev.get("place_id")
            pr = ev.get("place_refs")
            if not isinstance(pr, list) or not pr:
                continue

            for j, ref in enumerate(pr):
                if not isinstance(ref, dict):
                    continue
                refs_total += 1

                pv_id = ref.get("place_version_id")
                js = ref.get("jurisdiction_system_id")
                ref_pid = ref.get("place_id")

                if pv_id and pv_id not in place_versions:
                    refs_bad_pv.append((grp, rec_ptr, idx, j, pv_id))
                if js and js not in jurisdictions:
                    refs_bad_js.append((grp, rec_ptr, idx, j, js))
                if ref_pid and ref_pid not in places:
                    refs_bad_place.append((grp, rec_ptr, idx, j, ref_pid))

                temporal = ref.get("temporal")
                if isinstance(temporal, dict):
                    bucket = temporal.get("bucket")
                    if bucket == "year":
                        if temporal.get("open_ended") is True:
                            pass
                        else:
                            y = temporal.get("year")
                            if not isinstance(y, int) or y < 1 or y > 9999:
                                refs_bad_temporal.append((grp, rec_ptr, idx, j, temporal))
                    else:
                        # currently only year supported
                        refs_bad_temporal.append((grp, rec_ptr, idx, j, temporal))
                else:
                    refs_bad_temporal.append((grp, rec_ptr, idx, j, temporal))

                # In C.24.7 current semantics: place_refs interpret the same place_id
                if pid and ref_pid and ref_pid != pid:
                    # keep as warning-level, but fail for now to enforce canonical semantics
                    refs_bad_place.append((grp, rec_ptr, idx, j, f"ref.place_id={ref_pid!r} != event.place_id={pid!r}"))

if refs_bad_pv:
    print("[ERROR] event.place_refs reference missing place_version_id:", len(refs_bad_pv))
    for grp, rec_ptr, idx, j, pv_id in refs_bad_pv[:25]:
        print(f" - {grp}[{rec_ptr}].events[{idx}].place_refs[{j}].place_version_id={pv_id!r} missing")
    raise SystemExit(1)

if refs_bad_js:
    print("[ERROR] event.place_refs reference missing jurisdiction_system_id:", len(refs_bad_js))
    for grp, rec_ptr, idx, j, js in refs_bad_js[:25]:
        print(f" - {grp}[{rec_ptr}].events[{idx}].place_refs[{j}].jurisdiction_system_id={js!r} missing")
    raise SystemExit(1)

if refs_bad_place:
    print("[ERROR] event.place_refs reference invalid/mismatched place_id:", len(refs_bad_place))
    for item in refs_bad_place[:25]:
        grp, rec_ptr, idx, j, msg = item
        print(f" - {grp}[{rec_ptr}].events[{idx}].place_refs[{j}] {msg}")
    raise SystemExit(1)

if refs_bad_temporal:
    print("[ERROR] event.place_refs temporal invalid:", len(refs_bad_temporal))
    for grp, rec_ptr, idx, j, temporal in refs_bad_temporal[:25]:
        print(f" - {grp}[{rec_ptr}].events[{idx}].place_refs[{j}].temporal={temporal!r}")
    raise SystemExit(1)

print(f"[OK] C.24.7 linkage checks passed:")
print(f"     events_with_place_id={total_with_place_id}")
print(f"     place_versions={len(place_versions)} jurisdiction_systems={len(jurisdictions)} place_refs_total={refs_total}")
PY

########################################
# Final confirmation
########################################
echo
echo "=== C.24.7 VERIFICATION COMPLETE ==="
echo "Final canonical export:"
echo "  $OUTDIR/export_c24_7.json"
