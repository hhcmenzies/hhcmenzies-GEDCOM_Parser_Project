#!/usr/bin/env bash
set -euo pipefail

CONFIG="${1:-collections.json}"
UA="${2:-MA-Notables/1.0 (contact: you@example.com)}"

OUTROOT="${OUTROOT:-out/runs}"
RUN="$OUTROOT/$(date -u +%Y-%m-%dT%H%M%SZ)"
mkdir -p "$RUN"

echo "Config: $CONFIG"
echo "Run dir: $RUN"

python -m json.tool "$CONFIG" > /dev/null

# Strict local checks (no network needed)
python preflight_ma_notables.py --config "$CONFIG"

# Optional live checks:
#   CHECK_WIKIPEDIA=1 ./run_ma_notables.sh collections.json "UA..."
if [[ "${CHECK_WIKIPEDIA:-0}" == "1" ]]; then
  python preflight_ma_notables.py --config "$CONFIG" --check-wikipedia --user-agent "$UA" --sleep "${PREFLIGHT_SLEEP:-0.1}" --max-titles "${PREFLIGHT_MAX:-500}"
fi

python ma_notables_pipeline.py --config "$CONFIG" --outdir "$RUN" --user-agent "$UA"
ln -sfn "$(basename "$RUN")" "$OUTROOT/latest"

echo "Latest run: $RUN"
echo "MASTER:       $(readlink -f "$RUN/master_ma_1600_1799.jsonl")"
echo "QA REPORT:    $(readlink -f "$RUN/qa_report.json")"
echo "MANIFEST:     $(readlink -f "$RUN/manifest.json")"
echo "COLLECTIONS:  $(readlink -f "$RUN/collections")/"
