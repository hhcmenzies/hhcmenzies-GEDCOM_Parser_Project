#!/usr/bin/env bash
set -euo pipefail

########################################
# GEDCOM PARSER FULL APPLY SUITE (C.24.9)
# - Builds through C.24.7
# - Validates C.24.7 strict schema + linkage
# - Validates plan file + plan schema (if PLAN provided)
# - Runs C.24.9 applier (dry-run or apply)
# - Validates C.24.9 strict schema + linkage
#
# Environment overrides:
#   INPUT=mock_files/gedcom_1.ged
#   OUTDIR=outputs
#   CONFIG=config/gedcom_parser.yml
#   PLAN=plans/first_real_place_plan.json     (optional)
#   DRY_RUN=0|1                               (default 0)
#   VERBOSITY=0|1|2|3                         (default 2)
#   EXPECT_PLAN_PASS=0|1                      (default 1; only used if PLAN set)
#   FAIL_ON_SOFT=0|1                          (default 0)
#   FAIL_ON_ADVISORY=0|1                      (default 0)
########################################

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

INPUT="${INPUT:-$ROOT_DIR/mock_files/gedcom_1.ged}"
OUTDIR="${OUTDIR:-$ROOT_DIR/outputs}"
CONFIG="${CONFIG:-$ROOT_DIR/config/gedcom_parser.yml}"

PLAN="${PLAN:-}"
DRY_RUN="${DRY_RUN:-0}"
VERBOSITY="${VERBOSITY:-2}"
EXPECT_PLAN_PASS="${EXPECT_PLAN_PASS:-1}"
FAIL_ON_SOFT="${FAIL_ON_SOFT:-0}"
FAIL_ON_ADVISORY="${FAIL_ON_ADVISORY:-0}"

EXPORT0="$OUTDIR/export.json"
EXPORT1="$OUTDIR/export_xref.json"
EXPORT2="$OUTDIR/export_standardized.json"
EXPORT3="$OUTDIR/export_events_resolved.json"
EXPORT4="$OUTDIR/export_names_normalized.json"
EXPORT5="$OUTDIR/export_media_normalized.json"
EXPORT_C245="$OUTDIR/export_c24_5.json"
EXPORT_C246="$OUTDIR/export_c24_6.json"
EXPORT_C247="$OUTDIR/export_c24_7.json"
EXPORT_C249="$OUTDIR/export_c24_9.json"

REPORT_C249="${REPORT_C249:-$OUTDIR/place_plan_applier_report.json}"
REPORT_PLAN="${REPORT_PLAN:-$OUTDIR/place_plan_applier_plan_report.json}"

SCHEMA_C247_STRICT="${SCHEMA_C247_STRICT:-$ROOT_DIR/schemas/c24_7_canonical_export.strict.schema.json}"
SCHEMA_C249_STRICT="${SCHEMA_C249_STRICT:-$ROOT_DIR/schemas/c24_9_canonical_export.strict.schema.json}"
SCHEMA_PLAN="${SCHEMA_PLAN:-$ROOT_DIR/schemas/c24_9_place_plan.schema.json}"

echo "=== GEDCOM PARSER FULL APPLY SUITE (C.24.9) ==="
echo "Project root: $ROOT_DIR"
echo "Using input: $INPUT"
echo "Output directory: $OUTDIR"
echo "Config: $CONFIG"
if [[ -n "$PLAN" ]]; then
  echo "Plan: $PLAN"
  echo "EXPECT_PLAN_PASS: $EXPECT_PLAN_PASS"
  echo "DRY_RUN: $DRY_RUN"
  echo "VERBOSITY: $VERBOSITY"
fi
echo

mkdir -p "$OUTDIR"

########################################
# [0] Sanity checks
########################################
echo "[0] Sanity checks"

# Basic files
[[ -f "$INPUT" ]] || { echo "[ERROR] Input GEDCOM not found: $INPUT" >&2; exit 1; }
[[ -f "$CONFIG" ]] || { echo "[ERROR] Config not found: $CONFIG" >&2; exit 1; }

# Python deps (jsonschema used for validation)
python - <<'PY' >/dev/null
import sys
try:
    import jsonschema  # noqa
except Exception as e:
    print("[ERROR] Missing dependency: jsonschema. Install it into venv.", file=sys.stderr)
    raise
PY
echo "[OK] Dependencies present"

# Plan file preflight checks (only if PLAN is set)
if [[ -n "$PLAN" ]]; then
  [[ -f "$PLAN" ]] || { echo "[ERROR] Plan file not found: $PLAN" >&2; exit 1; }
  [[ -s "$PLAN" ]] || { echo "[ERROR] Plan file is empty: $PLAN" >&2; exit 1; }

  # First non-whitespace char sanity check (guards the JSONDecodeError: line 1 col 1)
  python - <<'PY'
import sys
path = sys.argv[1]
with open(path, "r", encoding="utf-8") as f:
    s = f.read()
t = s.lstrip()
if not t:
    print(f"[ERROR] Plan file has only whitespace: {path}", file=sys.stderr)
    raise SystemExit(1)
if t[0] not in "{[":
    print(f"[ERROR] Plan file does not look like JSON (first non-ws char={t[0]!r}): {path}", file=sys.stderr)
    raise SystemExit(1)
print("[OK] Plan file preflight checks passed")
PY "$PLAN"
fi

echo

########################################
# [1] Run main parser → export.json
########################################
echo "[1] Running main parser → export.json"
python -m gedcom_parser.main \
  -i "$INPUT" \
  -o "$EXPORT0"

########################################
# [2] XREF/UUID resolver → export_xref.json
########################################
echo "[2] Running xref_resolver → export_xref.json"
python -m gedcom_parser.enrichment.xref_resolver \
  -i "$EXPORT0" \
  -o "$EXPORT1"

########################################
# [3] Place standardization → export_standardized.json
########################################
echo "[3] Running place_standardizer → export_standardized.json"
python -m gedcom_parser.enrichment.place_standardizer \
  -i "$EXPORT1" \
  -o "$EXPORT2"

########################################
# [4] Event disambiguation → export_events_resolved.json
########################################
echo "[4] Running event_disambiguator → export_events_resolved.json"
python -m gedcom_parser.enrichment.event_disambiguator \
  "$EXPORT2" \
  -o "$EXPORT3"

########################################
# [5] Name normalization → export_names_normalized.json
########################################
echo "[5] Running name_normalization → export_names_normalized.json"
python -m gedcom_parser.normalization.name_normalization \
  -i "$EXPORT3" \
  -o "$EXPORT4"

########################################
# [6] Media normalization → export_media_normalized.json
########################################
echo "[6] Running media_normalizer → export_media_normalized.json"
python -m gedcom_parser.enrichment.media_normalizer \
  -i "$EXPORT4" \
  -o "$EXPORT5"

########################################
# [7] Place registry promotion (C.24.5) → export_c24_5.json
########################################
echo "[7] Running place_registry_builder → export_c24_5.json"
python -m gedcom_parser.enrichment.place_registry_builder \
  -i "$EXPORT5" \
  -o "$EXPORT_C245"

########################################
# [8] Place hierarchy build (C.24.6) → export_c24_6.json
########################################
echo "[8] Running place_hierarchy_builder → export_c24_6.json"
python -m gedcom_parser.enrichment.place_hierarchy_builder \
  -i "$EXPORT_C245" \
  -o "$EXPORT_C246"

########################################
# [9] Place versioning (C.24.7) → export_c24_7.json
########################################
echo "[9] Running place_version_builder → export_c24_7.json"
python -m gedcom_parser.enrichment.place_version_builder \
  -i "$EXPORT_C246" \
  -o "$EXPORT_C247" \
  --config "$CONFIG"

########################################
# [10] Strict JSON Schema validation (C.24.7)
########################################
echo "[10] Validating export_c24_7.json against strict JSON Schema"
python - <<'PY'
import json
from jsonschema import Draft202012Validator

schema_path = "schemas/c24_7_canonical_export.strict.schema.json"
doc_path = "outputs/export_c24_7.json"

schema = json.load(open(schema_path, "r", encoding="utf-8"))
doc = json.load(open(doc_path, "r", encoding="utf-8"))

validator = Draft202012Validator(schema)
errors = sorted(validator.iter_errors(doc), key=lambda e: e.path)

if errors:
    print("[ERROR] C.24.7 schema validation failed with", len(errors), "error(s). Showing first 25:")
    for e in errors[:25]:
        path = "$" + "".join(f"[{p!r}]" if isinstance(p, int) else f".{p}" for p in e.path)
        print("-", path, ":", e.message)
    raise SystemExit(1)

print("[OK] C.24.7 schema validation passed")
PY

########################################
# [11] Linkage checks (C.24.7) — places/place_versions/place_refs
########################################
echo "[11] Running C.24.7 linkage checks"
python - <<'PY'
import json

doc = json.load(open("outputs/export_c24_7.json","r",encoding="utf-8"))
places = doc.get("places", {}) or {}
pvs = doc.get("place_versions", {}) or {}
jss = doc.get("jurisdiction_systems", {}) or {}

missing_place = []
missing_pv = []
missing_js = []
refs_total = 0
events_with_place_id = 0

def check_ref(ctx, ref):
    global refs_total
    refs_total += 1
    pid = ref.get("place_id")
    pvid = ref.get("place_version_id")
    jsid = ref.get("jurisdiction_system_id")
    if pid and pid not in places:
        missing_place.append((ctx, pid))
    if pvid and pvid not in pvs:
        missing_pv.append((ctx, pvid))
    if jsid and jsid not in jss:
        missing_js.append((ctx, jsid))

for grp in ("individuals", "families"):
    for rec_ptr, rec in (doc.get(grp, {}) or {}).items():
        for idx, ev in enumerate(rec.get("events", []) or []):
            if not isinstance(ev, dict):
                continue
            pid = ev.get("place_id")
            if pid:
                events_with_place_id += 1
                if pid not in places:
                    missing_place.append((f"{grp}[{rec_ptr}].events[{idx}].place_id", pid))
            prs = ev.get("place_refs")
            if isinstance(prs, list):
                for j, ref in enumerate(prs):
                    if isinstance(ref, dict):
                        check_ref(f"{grp}[{rec_ptr}].events[{idx}].place_refs[{j}]", ref)

if missing_place or missing_pv or missing_js:
    print("[ERROR] C.24.7 linkage failures:")
    if missing_place:
        print(" - missing place_id references:", len(missing_place))
        for ctx,pid in missing_place[:25]:
            print("   ", ctx, "->", pid)
    if missing_pv:
        print(" - missing place_version_id references:", len(missing_pv))
        for ctx,pvid in missing_pv[:25]:
            print("   ", ctx, "->", pvid)
    if missing_js:
        print(" - missing jurisdiction_system_id references:", len(missing_js))
        for ctx,jsid in missing_js[:25]:
            print("   ", ctx, "->", jsid)
    raise SystemExit(1)

print("[OK] C.24.7 linkage checks passed:")
print("     events_with_place_id=", events_with_place_id)
print("     place_versions=", len(pvs), "jurisdiction_systems=", len(jss), "place_refs_total=", refs_total)
PY

########################################
# [12] If PLAN is set: validate plan schema, then run applier
########################################
if [[ -n "$PLAN" ]]; then
  echo "[12] Validating plan against JSON Schema"
  python - <<'PY'
import json
from jsonschema import Draft202012Validator

schema_path = "schemas/c24_9_place_plan.schema.json"
plan_path = __import__("sys").argv[1]

schema = json.load(open(schema_path, "r", encoding="utf-8"))
plan = json.load(open(plan_path, "r", encoding="utf-8"))

validator = Draft202012Validator(schema)
errors = sorted(validator.iter_errors(plan), key=lambda e: e.path)
if errors:
    print("[ERROR] Plan schema validation failed with", len(errors), "error(s). Showing first 25:")
    for e in errors[:25]:
        path = "$" + "".join(f"[{p!r}]" if isinstance(p, int) else f".{p}" for p in e.path)
        print("-", path, ":", e.message)
    raise SystemExit(1)
print("[OK] Plan schema validation passed")
PY "$PLAN"

  echo "[13] Running place_plan_applier → export_c24_9.json"
  APPLIER_ARGS=( -i "$EXPORT_C247" -o "$EXPORT_C249" -p "$PLAN" --verbosity "$VERBOSITY" --report "$REPORT_PLAN" )
  if [[ "$DRY_RUN" == "1" ]]; then
    echo "[INFO] Dry-run mode enabled"
    APPLIER_ARGS+=( --dry-run )
  fi
  if [[ "$FAIL_ON_SOFT" == "1" ]]; then
    APPLIER_ARGS+=( --fail-on-soft )
  fi
  if [[ "$FAIL_ON_ADVISORY" == "1" ]]; then
    APPLIER_ARGS+=( --fail-on-advisory )
  fi

  set +e
  python -m gedcom_parser.enrichment.place_plan_applier "${APPLIER_ARGS[@]}"
  RC=$?
  set -e

  if [[ "$EXPECT_PLAN_PASS" == "1" ]]; then
    if [[ "$RC" -ne 0 ]]; then
      echo "[ERROR] Plan application failed but EXPECT_PLAN_PASS=1" >&2
      exit 1
    fi
  else
    if [[ "$RC" -eq 0 ]]; then
      echo "[ERROR] Plan application succeeded but EXPECT_PLAN_PASS=0 (expected failure)" >&2
      exit 1
    fi
    echo "[OK] Plan application failed as expected (EXPECT_PLAN_PASS=0)"
  fi

  echo "[14] Validating export_c24_9.json against strict JSON Schema"
  python - <<'PY'
import json
from jsonschema import Draft202012Validator

schema_path = "schemas/c24_9_canonical_export.strict.schema.json"
doc_path = "outputs/export_c24_9.json"

schema = json.load(open(schema_path, "r", encoding="utf-8"))
doc = json.load(open(doc_path, "r", encoding="utf-8"))

validator = Draft202012Validator(schema)
errors = sorted(validator.iter_errors(doc), key=lambda e: e.path)

if errors:
    print("[ERROR] C.24.9 schema validation failed with", len(errors), "error(s). Showing first 25:")
    for e in errors[:25]:
        path = "$" + "".join(f"[{p!r}]" if isinstance(p, int) else f".{p}" for p in e.path)
        print("-", path, ":", e.message)
    raise SystemExit(1)

print("[OK] C.24.9 schema validation passed")
PY

  echo "[15] Linkage checks (C.24.9) — redirects/ops/audit refs"
  python - <<'PY'
import json

doc = json.load(open("outputs/export_c24_9.json","r",encoding="utf-8"))
places = doc.get("places", {}) or {}
pvs = doc.get("place_versions", {}) or {}
jss = doc.get("jurisdiction_systems", {}) or {}

pr = doc.get("place_redirects", {}) or {}
pvr = doc.get("place_version_redirects", {}) or {}
ops = doc.get("place_operations", []) or []
audit = doc.get("place_audit", []) or []

errs = []

def place_ok(pid): return isinstance(pid,str) and pid in places
def pv_ok(pvid): return isinstance(pvid,str) and pvid in pvs
def js_ok(jsid): return not jsid or (isinstance(jsid,str) and jsid in jss)

# place_redirects: from -> entries with to_place_id
if not isinstance(pr, dict):
    errs.append("root.place_redirects must be an object")
else:
    for from_pid, arr in pr.items():
        if not place_ok(from_pid):
            errs.append(f"place_redirects from_place_id missing: {from_pid!r}")
        if not isinstance(arr, list):
            errs.append(f"place_redirects[{from_pid!r}] must be an array")
            continue
        for i, r in enumerate(arr):
            if not isinstance(r, dict):
                errs.append(f"place_redirects[{from_pid!r}][{i}] must be an object")
                continue
            to_pid = r.get("to_place_id")
            if not place_ok(to_pid):
                errs.append(f"place_redirects[{from_pid!r}][{i}].to_place_id missing: {to_pid!r}")
            jsid = r.get("jurisdiction_system_id")
            if jsid and not js_ok(jsid):
                errs.append(f"place_redirects[{from_pid!r}][{i}].jurisdiction_system_id missing: {jsid!r}")

# place_version_redirects: pv_from -> entries with to_place_version_id
if not isinstance(pvr, dict):
    errs.append("root.place_version_redirects must be an object")
else:
    for from_pv, arr in pvr.items():
        if not pv_ok(from_pv):
            errs.append(f"place_version_redirects from_place_version_id missing: {from_pv!r}")
        if not isinstance(arr, list):
            errs.append(f"place_version_redirects[{from_pv!r}] must be an array")
            continue
        for i, r in enumerate(arr):
            if not isinstance(r, dict):
                errs.append(f"place_version_redirects[{from_pv!r}][{i}] must be an object")
                continue
            to_pv = r.get("to_place_version_id")
            if not pv_ok(to_pv):
                errs.append(f"place_version_redirects[{from_pv!r}][{i}].to_place_version_id missing: {to_pv!r}")
            jsid = r.get("jurisdiction_system_id")
            if jsid and not js_ok(jsid):
                errs.append(f"place_version_redirects[{from_pv!r}][{i}].jurisdiction_system_id missing: {jsid!r}")

# place_operations: ensure referenced ids exist (best-effort without dictating your full op schema)
if not isinstance(ops, list):
    errs.append("root.place_operations must be an array")
else:
    for i, op in enumerate(ops):
        if not isinstance(op, dict):
            errs.append(f"place_operations[{i}] must be an object")
            continue
        jsid = op.get("jurisdiction_system_id")
        if jsid and not js_ok(jsid):
            errs.append(f"place_operations[{i}].jurisdiction_system_id missing: {jsid!r}")
        for k in ("from_place_id","to_place_id"):
            if k in op and op[k] and not place_ok(op[k]):
                errs.append(f"place_operations[{i}].{k} missing: {op[k]!r}")
        for k in ("from_place_ids","to_place_ids"):
            if k in op and isinstance(op[k], list):
                for pid in op[k]:
                    if pid and not place_ok(pid):
                        errs.append(f"place_operations[{i}].{k} missing: {pid!r}")

# audit: basic shape check
if not isinstance(audit, list):
    errs.append("root.place_audit must be an array")

if errs:
    print("[ERROR] C.24.9 linkage checks failed with", len(errs), "issue(s). Showing first 50:")
    for e in errs[:50]:
        print(" -", e)
    raise SystemExit(1)

print("[OK] C.24.9 linkage checks passed:")
print("     place_redirects_sources=", len(pr) if isinstance(pr,dict) else "n/a")
print("     place_version_redirects_sources=", len(pvr) if isinstance(pvr,dict) else "n/a")
print("     operations=", len(ops) if isinstance(ops,list) else "n/a")
print("     audit_entries=", len(audit) if isinstance(audit,list) else "n/a")
PY

fi

echo
echo "=== C.24.9 APPLY SUITE COMPLETE ==="
echo "Final canonical export (C.24.7):"
echo "  $EXPORT_C247"
if [[ -n "$PLAN" ]]; then
  echo "Applied export (C.24.9):"
  echo "  $EXPORT_C249"
  echo "Plan report:"
  echo "  $REPORT_PLAN"
