#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-out/runs/latest}"

echo "== Listing =="
ls -la "$ROOT" | sed -n '1,200p' || true
echo
echo "== Collections =="
ls -la "$ROOT/collections" | sed -n '1,200p' || true
echo
echo "== Line counts =="
wc -l "$ROOT/master_ma_1600_1799.jsonl" || true
wc -l "$ROOT/collections"/*.jsonl | sort -n || true
echo
echo "== Quarantine =="
wc -l "$ROOT"/rejected_*.jsonl || true
echo
echo "== Quick JSON parse sample (master first 50) =="
python - <<'PY'
import json, sys
p=sys.argv[1]
ok=0
with open(p,'r',encoding='utf-8') as f:
    for i,line in enumerate(f, start=1):
        if i>50: break
        json.loads(line)
        ok += 1
print("Parsed JSON lines:", ok, "from", p)
PY "$ROOT/master_ma_1600_1799.jsonl"
