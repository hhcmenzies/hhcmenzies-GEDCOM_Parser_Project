#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

echo "=== GEDCOM PARSER FULL PIPELINE (up to C.24.4.9) ==="
echo "Root: $ROOT_DIR"

# Allow custom GEDCOM as first arg, default to mock_files/gedcom_1.ged
INPUT="${1:-mock_files/gedcom_1.ged}"
OUTDIR="$ROOT_DIR/outputs"

echo
echo "[0] Cleaning caches (__pycache__, *.pyc)"
find "$ROOT_DIR" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find "$ROOT_DIR" -name "*.pyc" -delete 2>/dev/null || true

mkdir -p "$OUTDIR" "$ROOT_DIR/logs"

export PYTHONPATH="$ROOT_DIR/src"

echo
echo "[1] Main parser → export.json"
python -m gedcom_parser.main \
  -i "$INPUT" \
  -o "$OUTDIR/export.json" \
  --debug

echo
echo "[2] XREF resolver → export_xref.json"
python -m gedcom_parser.postprocess.xref_resolver \
  -i "$OUTDIR/export.json" \
  -o "$OUTDIR/export_xref.json" \
  --debug

echo
echo "[3] Place standardizer → export_standardized.json"
python -m gedcom_parser.postprocess.place_standardizer \
  -i "$OUTDIR/export_xref.json" \
  -o "$OUTDIR/export_standardized.json" \
  --debug

echo
echo "[4] Event disambiguator → export_events_resolved.json"
python -m gedcom_parser.postprocess.event_disambiguator \
  "$OUTDIR/export_standardized.json" \
  -o "$OUTDIR/export_events_resolved.json" \
  --debug

echo
echo "[5] Event scoring → export_scored.json + event_scores.json + scoring_summary.json"
python -m gedcom_parser.postprocess.event_scoring \
  "$OUTDIR/export_events_resolved.json" \
  -o "$OUTDIR/export_scored.json" \
  --event-scores "$OUTDIR/event_scores.json" \
  --summary "$OUTDIR/scoring_summary.json" \
  --debug

echo
echo "[6] Outputs:"
ls -lh "$OUTDIR"/export*.json "$OUTDIR"/event_scores.json "$OUTDIR"/scoring_summary.json

echo
echo "[7] Tail of key logs:"
for f in main.log xref_resolver.log place_standardizer.log event_disambiguator.log event_scoring.log; do
  if [[ -f "logs/$f" ]]; then
    echo
    echo "--- logs/$f ---"
    tail -n 5 "logs/$f" || true
  fi
done

echo
echo "=== PIPELINE COMPLETE ==="
