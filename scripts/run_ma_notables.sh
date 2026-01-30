#!/usr/bin/env bash
set -euo pipefail

CONFIG="${1:-collections.json}"
USER_AGENT="${2:-MA-Notables/1.0 (contact: you@example.com)}"
CHECK_WIKIPEDIA="${3:-0}"   # set to 1 to enable live Wikipedia title checks
SLEEP="${SLEEP:-0.1}"
MAX_TITLES="${MAX_TITLES:-500}"

echo "Config: $CONFIG"
echo "Run dir: out/runs/$(date -u +%Y-%m-%dT%H%M%SZ)"

# Preflight (schema + optional Wikipedia checks)
if [[ "$CHECK_WIKIPEDIA" == "1" ]]; then
  python preflight_ma_notables.py --config "$CONFIG" --user-agent "$USER_AGENT" --check-wikipedia --sleep "$SLEEP" --max-titles "$MAX_TITLES"
else
  python preflight_ma_notables.py --config "$CONFIG" --user-agent "$USER_AGENT"
fi

RUN="out/runs/$(date -u +%Y-%m-%dT%H%M%SZ)"
mkdir -p "$RUN"

python ma_notables_pipeline.py --config "$CONFIG" --outdir "$RUN" --user-agent "$USER_AGENT"

ln -sfn "$(basename "$RUN")" out/runs/latest
echo "Latest run: $RUN"

# Convenience: show where outputs are
echo "RUN DIR:     $(readlink -f "$RUN")"
echo "MASTER:      $(readlink -f "$RUN/master_ma_1600_1799.jsonl" 2>/dev/null || true)"
echo "QA:          $(readlink -f "$RUN/qa_report.json" 2>/dev/null || true)"
echo "MANIFEST:    $(readlink -f "$RUN/manifest.json" 2>/dev/null || true)"
echo "COLLECTIONS: $(readlink -f "$RUN/collections" 2>/dev/null || true)"
