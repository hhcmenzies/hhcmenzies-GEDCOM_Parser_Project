#!/usr/bin/env bash
set -euo pipefail

########################################
# GEDCOM PARSER FULL VERIFICATION SUITE (C.24.8)
# - Builds canonical export through C.24.7
# - Validates against C.24.7 strict schema
# - Runs C.24.8 merge/split verifier (diagnostics + optional plan validation)
########################################

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

INPUT="${INPUT:-$ROOT_DIR/mock_files/gedcom_1.ged}"
OUTDIR="${OUTDIR:-$ROOT_DIR/outputs}"
CONFIG="${CONFIG:-$ROOT_DIR/config/gedcom_parser.yml}"

# Optional:
#   PLAN="merge_plan.json" ./verify_all_C24_8.sh
PLAN="${PLAN:-}"

# If PLAN is provided, default behavior is to FAIL the suite if verifier fails.
# Set EXPECT_PLAN_PASS=0 if you EXPECT the plan to fail (e.g., demo plan with fake ids).
EXPECT_PLAN_PASS="${EXPECT_PLAN_PASS:-1}"

echo "=== GEDCOM PARSER FULL VERIFICATION SUITE (C.24.8) ==="
echo "Using input: $INPUT"
echo "Output directory: $OUTDIR"
echo "Config: $CONFIG"
if [[ -n "${PLAN}" ]]; then
  echo "Plan: $PLAN"
  echo "EXPECT_PLAN_PASS: $EXPECT_PLAN_PASS"
fi
echo

mkdir -p "$OUTDIR"

########################################
# [0] Sanity checks
########################################
echo "[0] Sanity checks"
if [[ ! -f "$INPUT" ]]; then
  echo "[ERROR] Input GEDCOM not found: $INPUT"
  exit 1
fi

if [[ ! -f "$CONFIG" ]]; then
  echo "[ERROR] Config not found: $CONFIG"
  exit 1
fi

if [[ -n "${PLAN}" && ! -f "${PLAN}" ]]; then
  echo "[ERROR] Plan file not found: ${PLAN}"
  exit 1
fi

# Ensure jsonschema is available (used for schema validation)
python - << 'PY'
import sys
try:
    import jsonschema  # noqa: F401
except Exception as e:
    print("[ERROR] Missing dependency: jsonschema. Install it (pip install jsonschema).")
    raise
print("[OK] Dependencies present")
PY

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
python -m gedcom_parser.enrichment.xref_resolver \
  -i "$OUTDIR/export.json" \
  -o "$OUTDIR/export_xref.json"

########################################
# [3] Place standardization → export_standardized.json
########################################
echo "[3] Running place_standardizer → export_standardized.json"
python -m gedcom_parser.enrichment.place_standardizer \
  -i "$OUTDIR/export_xref.json" \
  -o "$OUTDIR/export_standardized.json"

########################################
# [4] Event disambiguation → export_events_resolved.json
########################################
echo "[4] Running event_disambiguator → export_events_resolved.json"
python -m gedcom_parser.enrichment.event_disambiguator \
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
python -m gedcom_parser.enrichment.media_normalizer \
  -i "$OUTDIR/export_names_normalized.json" \
  -o "$OUTDIR/export_media_normalized.json"

########################################
# [7] Place registry promotion (C.24.5) → export_c24_5.json
########################################
echo "[7] Running place_registry_builder → export_c24_5.json"
python -m gedcom_parser.enrichment.place_registry_builder \
  -i "$OUTDIR/export_media_normalized.json" \
  -o "$OUTDIR/export_c24_5.json"

########################################
# [8] Place hierarchy build (C.24.6) → export_c24_6.json
########################################
echo "[8] Running place_hierarchy_builder → export_c24_6.json"
python -m gedcom_parser.enrichment.place_hierarchy_builder \
  -i "$OUTDIR/export_c24_5.json" \
  -o "$OUTDIR/export_c24_6.json"

########################################
# [9] Place versioning (C.24.7) → export_c24_7.json
########################################
echo "[9] Running place_version_builder → export_c24_7.json"
python -m gedcom_parser.enrichment.place_version_builder \
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
jur_sys = doc.get("jurisdiction_systems", {}) or {}

missing_place = 0
missing_pv = 0
events_with_pid = 0
place_refs_total = 0

for grp in ("individuals", "families"):
    for rec in (doc.get(grp, {}) or {}).values():
        for ev in (rec.get("events", []) or []):
            if not isinstance(ev, dict):
                continue
            pid = ev.get("place_id")
            if pid:
                events_with_pid += 1
                if pid not in places:
                    missing_place += 1

            pr = ev.get("place_refs")
            if isinstance(pr, list):
                for ref in pr:
                    if not isinstance(ref, dict):
                        continue
                    place_refs_total += 1
                    pv_id = ref.get("place_version_id")
                    if pv_id and pv_id not in place_versions:
                        missing_pv += 1

if missing_place:
    print(f"[ERROR] events with place_id missing from root.places: {missing_place}")
    raise SystemExit(1)

if missing_pv:
    print(f"[ERROR] place_refs referencing missing place_versions: {missing_pv}")
    raise SystemExit(1)

print("[OK] C.24.7 linkage checks passed:")
print(f"     events_with_place_id={events_with_pid}")
print(f"     place_versions={len(place_versions)} jurisdiction_systems={len(jur_sys)} place_refs_total={place_refs_total}")
PY

########################################
# [12] Merge/split verifier diagnostics (C.24.8)
########################################
echo "[12] Running place_merge_split_verifier (diagnostics) → place_merge_split_report.json"
python -m gedcom_parser.enrichment.place_merge_split_verifier \
  -i "$OUTDIR/export_c24_7.json" \
  --report "$OUTDIR/place_merge_split_report.json"

########################################
# [13] Optional: validate a merge/split plan (C.24.8)
########################################
if [[ -n "${PLAN}" ]]; then
  echo "[13] Running place_merge_split_verifier with plan → place_merge_split_plan_report.json"
  set +e
  python -m gedcom_parser.enrichment.place_merge_split_verifier \
    -i "$OUTDIR/export_c24_7.json" \
    --plan "$PLAN" \
    --report "$OUTDIR/place_merge_split_plan_report.json"
  rc=$?
  set -e

  if [[ "$EXPECT_PLAN_PASS" == "1" ]]; then
    if [[ "$rc" != "0" ]]; then
      echo "[ERROR] Plan verification failed but EXPECT_PLAN_PASS=1"
      exit "$rc"
    fi
    echo "[OK] Plan verification passed"
  else
    if [[ "$rc" == "0" ]]; then
      echo "[ERROR] Plan verification passed but EXPECT_PLAN_PASS=0 (expected failure)"
      exit 1
    fi
    echo "[OK] Plan verification failed as expected (EXPECT_PLAN_PASS=0)"
  fi
fi

########################################
# Final confirmation
########################################
echo
echo "=== C.24.8 VERIFICATION COMPLETE ==="
echo "Final canonical export (C.24.7):"
echo "  $OUTDIR/export_c24_7.json"
echo "Verifier report:"
echo "  $OUTDIR/place_merge_split_report.json"
if [[ -n "${PLAN}" ]]; then
  echo "Plan report:"
  echo "  $OUTDIR/place_merge_split_plan_report.json"
fi
