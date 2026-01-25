#!/usr/bin/env bash
set -euo pipefail
CONFIG="${1:-collections.json}"
UA="${2:-MA-Notables/1.0 (contact: david.menzies@gmail.com)}"

python -m json.tool "$CONFIG" > /dev/null
python preflight_ma_notables.py --config "$CONFIG"

RUN="out/runs/$(date -u +%Y-%m-%dT%H%M%SZ)"
mkdir -p "$RUN"

python ma_notables_pipeline.py \
  --config "$CONFIG" \
  --outdir "$RUN" \
  --user-agent "$UA"

ln -sfn "$(basename "$RUN")" out/runs/latest
echo "Latest run: $RUN"
