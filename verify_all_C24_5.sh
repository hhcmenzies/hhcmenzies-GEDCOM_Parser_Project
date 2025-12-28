#!/usr/bin/env bash
set -euo pipefail

########################################
# Configuration
########################################
BASE="$(cd "$(dirname "$0")" && pwd)"
SRC="$BASE/src"
OUTDIR="$BASE/outputs"
SCHEMADIR="$BASE/schemas"
INPUT="$BASE/mock_files/gedcom_1.ged"

export PYTHONPATH="$SRC"

echo "=== GEDCOM PARSER FULL VERIFICATION SUITE (C.24.5) ==="
echo "Using input: $INPUT"
echo "Output directory: $OUTDIR"
echo

mkdir -p "$OUTDIR"

########################################
# [1] Main parser
########################################
echo "[1] Running main parser → export.json"
python -m gedcom_parser.main \
  -i "$INPUT" \
  -o "$OUTDIR/export.json"

########################################
# [2] XREF / UUID resolver
########################################
echo "[2] Running xref_resolver → export_xref.json"
python -m gedcom_parser.postprocess.xref_resolver \
  "$OUTDIR/export.json" \
  -o "$OUTDIR/export_xref.json"

########################################
# [3] Place standardization
########################################
echo "[3] Running place_standardizer → export_standardized.json"
python -m gedcom_parser.postprocess.place_standardizer \
  -i "$OUTDIR/export_xref.json" \
  -o "$OUTDIR/export_standardized.json"

########################################
# [4] Event disambiguation
########################################
echo "[4] Running event_disambiguator → export_events_resolved.json"
python -m gedcom_parser.postprocess.event_disambiguator \
  "$OUTDIR/export_standardized.json" \
  -o "$OUTDIR/export_events_resolved.json"

########################################
# [5] Name normalization
########################################
echo "[5] Running name_normalization → export_names_normalized.json"
python -m gedcom_parser.normalization.name_normalization \
  -i "$OUTDIR/export_events_resolved.json" \
  -o "$OUTDIR/export_names_normalized.json"

########################################
# [6] Media normalization (OBJE → first-class)
########################################
echo "[6] Running media_normalizer → export_media_normalized.json"
python -m gedcom_parser.postprocess.media_normalizer \
  -i "$OUTDIR/export_names_normalized.json" \
  -o "$OUTDIR/export_media_normalized.json"

########################################
# [7] Place registry promotion (C.24.5)
########################################
echo "[7] Running place_registry_builder → export_c24_5.json"
python -m gedcom_parser.postprocess.place_registry_builder \
  -i "$OUTDIR/export_media_normalized.json" \
  -o "$OUTDIR/export_c24_5.json"

########################################
# [8] Strict JSON Schema validation
########################################
echo "[8] Validating export_c24_5.json against strict JSON Schema"

python - << 'PY'
import json
from jsonschema import Draft202012Validator

schema_path = "schemas/c24_5_canonical_export.strict.schema.json"
doc_path = "outputs/export_c24_5.json"

schema = json.load(open(schema_path, "r", encoding="utf-8"))
doc = json.load(open(doc_path, "r", encoding="utf-8"))

validator = Draft202012Validator(schema)
errors = sorted(validator.iter_errors(doc), key=lambda e: e.path)

if errors:
    print("[ERROR] Schema validation failed with", len(errors), "error(s). Showing first 25:")
    for e in errors[:25]:
        path = "$" + "".join(
            f"[{p!r}]" if isinstance(p, int) else f".{p}" for p in e.path
        )
        print("-", path, ":", e.message)
    raise SystemExit(1)

print("[OK] Schema validation passed")
PY

########################################
# Final confirmation
########################################
echo
echo "=== C.24.5 VERIFICATION COMPLETE ==="
echo "Final canonical export:"
echo "  $OUTDIR/export_c24_5.json"
