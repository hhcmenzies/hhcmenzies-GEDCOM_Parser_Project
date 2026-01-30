#!/usr/bin/env python3
"""
place_plan_applier.py

C.24.9 – Place Plan Applier (AUDIT + APPLICATION MODEL)

Goal
----
Apply a C.24.9 place plan (merges/splits/supersede operations) to a C.24.7 canonical export
to produce a C.24.9 canonical export that includes:

- root.place_redirects   (redirect rules; DAG expectation; no cycles ideally)
- root.place_operations  (ledger of operations; applied/failed/dry-run)
- root.place_audit       (audit records; severity: hard/soft/advisory)
- root.place_audit_summary

Principles
----------
- Deterministic.
- Additive: does not delete existing registries (but may add/extend place_redirects).
- Policy-driven severity (hard/soft/advisory).
- Optional strict modes to fail on soft/advisory.
- Supports diagnostics-only (plan omitted) to emit audit summary on existing export.

Compatibility notes
-------------------
- Input is expected to be C.24.7 export (has places + place_versions + jurisdiction_systems).
- Output is a C.24.9 export: does not require place graph rewrite yet (that comes later).
- Redirect rules may target either place_id or place_version_id depending on entity_kind.

Operational semantics
---------------------
- merge / supersede:
    Creates redirect rules from each "from" id -> "to" id, scoped by jurisdiction + temporal
    if provided, otherwise open-ended scope (audit will flag open-ended as advisory).
- split:
    Does NOT automatically create redirects (because it is inherently 1->many ambiguous).
    It is recorded in place_operations and audited; future allocation rules can be added.

CLI
---
Diagnostics only:
  python -m gedcom_parser.enrichment.place_plan_applier -i outputs/export_c24_7.json -o outputs/export_c24_9.json

Apply plan:
  python -m gedcom_parser.enrichment.place_plan_applier -i outputs/export_c24_7.json -p merge_plan.json -o outputs/export_c24_9.json

Strictness:
  --fail-on-soft
  --fail-on-advisory
  --dry-run
  --verbosity 0..3

Optional schema validation if jsonschema installed:
  --schema-export schemas/c24_9_canonical_export.strict.schema.json
  --schema-plan   schemas/c24_9_place_plan.schema.json

This module is designed to pair with place_merge_split_verifier.py (C.24.8).
"""

from __future__ import annotations

import argparse
import copy
import datetime as _dt
import json
import os
from typing import Any, Dict, List, Optional, Tuple

from gedcom_parser.logger import get_logger

log = get_logger("place_plan_applier")

# ---------------------------------------------------------------------------
# Severity model (Option C)
# ---------------------------------------------------------------------------

SEV_HARD = "hard"
SEV_SOFT = "soft"
SEV_ADVISORY = "advisory"
SEVERITIES = (SEV_HARD, SEV_SOFT, SEV_ADVISORY)


def _utc_now_iso() -> str:
    return _dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _as_dict(v: Any) -> Optional[Dict[str, Any]]:
    return v if isinstance(v, dict) else None


def _as_list(v: Any) -> Optional[List[Any]]:
    return v if isinstance(v, list) else None


def _ensure_list(root: Dict[str, Any], key: str) -> List[Any]:
    v = root.get(key)
    if isinstance(v, list):
        return v
    root[key] = []
    return root[key]


def _ensure_dict(root: Dict[str, Any], key: str) -> Dict[str, Any]:
    v = root.get(key)
    if isinstance(v, dict):
        return v
    root[key] = {}
    return root[key]


def _jsonschema_validate_if_available(doc: Any, schema_path: str) -> List[str]:
    """
    Returns list of error strings. If jsonschema not installed or schema missing, returns [].
    """
    if not schema_path or not os.path.exists(schema_path):
        return []
    try:
        from jsonschema import Draft202012Validator  # type: ignore
    except Exception:
        return []
    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        v = Draft202012Validator(schema)
        errs = sorted(v.iter_errors(doc), key=lambda e: e.path)
        out: List[str] = []
        for e in errs[:200]:
            path = "$" + "".join(
                f"[{p!r}]" if isinstance(p, int) else f".{p}" for p in e.path
            )
            out.append(f"{path}: {e.message}")
        if len(errs) > 200:
            out.append(f"... ({len(errs) - 200} more)")
        return out
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Temporal helpers (year bucket)
# ---------------------------------------------------------------------------

def _parse_temporal(t: Any) -> Tuple[Optional[int], Optional[int], bool]:
    """
    Returns (start_year, end_year, open_ended).
    Supports:
      {bucket:"year", year: 1912}
      {bucket:"year", start_year: 1800, end_year: 1820}
      {bucket:"year", open_ended:true}
    """
    if not isinstance(t, dict):
        return (None, None, True)

    if t.get("open_ended") is True:
        return (None, None, True)

    y = t.get("year")
    if isinstance(y, int):
        return (y, y, False)

    sy = t.get("start_year")
    ey = t.get("end_year")
    if isinstance(sy, int) or isinstance(ey, int):
        s = sy if isinstance(sy, int) else None
        e = ey if isinstance(ey, int) else None
        # If any bound exists, treat as not fully open-ended
        return (s, e, False)

    # Default to open-ended when unknown
    return (None, None, True)


def _make_temporal_block(start: Optional[int], end: Optional[int], open_ended: bool) -> Dict[str, Any]:
    if open_ended:
        return {"bucket": "year", "open_ended": True}
    if start is not None and end is not None and start == end:
        return {"bucket": "year", "year": int(start)}
    t: Dict[str, Any] = {"bucket": "year"}
    if start is not None:
        t["start_year"] = int(start)
    if end is not None:
        t["end_year"] = int(end)
    if start is None and end is None:
        t["open_ended"] = True
    return t


# ---------------------------------------------------------------------------
# Audit records
# ---------------------------------------------------------------------------

def _audit_record(
    *,
    severity: str,
    code: str,
    message: str,
    op_id: Optional[str] = None,
    path: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if severity not in SEVERITIES:
        severity = SEV_ADVISORY
    rec: Dict[str, Any] = {
        "severity": severity,
        "code": code,
        "message": message,
        "timestamp": _utc_now_iso(),
    }
    if op_id:
        rec["op_id"] = op_id
    if path:
        rec["path"] = path
    if details:
        rec["details"] = details
    return rec


def _audit_counts(audit: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = {SEV_HARD: 0, SEV_SOFT: 0, SEV_ADVISORY: 0, "total": 0}
    for a in audit:
        sev = a.get("severity")
        if sev in (SEV_HARD, SEV_SOFT, SEV_ADVISORY):
            counts[sev] += 1
        counts["total"] += 1
    return counts


# ---------------------------------------------------------------------------
# Core applier
# ---------------------------------------------------------------------------

def apply_place_plan(
    export_root: Dict[str, Any],
    plan: Optional[Dict[str, Any]],
    *,
    dry_run: bool = False,
    verbosity: int = 1,
    fail_on_soft: bool = False,
    fail_on_advisory: bool = False,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Returns (new_export_root, report).
    The report contains:
      - audit[] + audit_summary
      - operations_applied counters
      - redirects_added counters
      - plan_validated bool
    """
    # Work on a copy so we never mutate caller state
    root = copy.deepcopy(export_root)

    audit: List[Dict[str, Any]] = []
    report: Dict[str, Any] = {
        "timestamp": _utc_now_iso(),
        "dry_run": bool(dry_run),
        "plan_present": bool(plan),
        "plan_validated": False,
        "operations_seen": 0,
        "operations_applied": 0,
        "operations_failed": 0,
        "redirect_rules_added": 0,
        "redirect_sources_touched": 0,
        "notes": [],
    }

    # Expected registries in C.24.7
    places = root.get("places", {})
    place_versions = root.get("place_versions", {})
    jurisdiction_systems = root.get("jurisdiction_systems", {})

    if not isinstance(places, dict):
        audit.append(_audit_record(
            severity=SEV_HARD,
            code="EXPORT_MISSING_PLACES",
            message="root.places missing or not an object; cannot apply plan safely",
            path="$.places",
        ))
        places = {}
    if not isinstance(place_versions, dict):
        audit.append(_audit_record(
            severity=SEV_SOFT,
            code="EXPORT_MISSING_PLACE_VERSIONS",
            message="root.place_versions missing or not an object; place_version operations cannot be validated",
            path="$.place_versions",
        ))
        place_versions = {}
    if jurisdiction_systems is not None and not isinstance(jurisdiction_systems, dict):
        audit.append(_audit_record(
            severity=SEV_SOFT,
            code="EXPORT_BAD_JURISDICTION_SYSTEMS",
            message="root.jurisdiction_systems must be an object when present",
            path="$.jurisdiction_systems",
        ))
        jurisdiction_systems = {}

    # Ensure C.24.9 registries exist (additive)
    place_redirects = _ensure_dict(root, "place_redirects")
    place_version_redirects = _ensure_dict(root, "place_version_redirects")
    place_operations = _ensure_list(root, "place_operations")
    place_audit = _ensure_list(root, "place_audit")

    # Helper existence checks
    def place_id_exists(pid: str) -> bool:
        return isinstance(pid, str) and pid in places

    def place_version_exists(pvid: str) -> bool:
        return isinstance(pvid, str) and pvid in place_versions

    def jurisdiction_exists(js: str) -> bool:
        return isinstance(js, str) and js in (jurisdiction_systems or {})

    # -----------------------------------------------------------------------
    # Plan parsing / normalization
    # -----------------------------------------------------------------------
    ops_in_plan: List[Dict[str, Any]] = []
    policy: Dict[str, Any] = {}

    if plan is None:
        # Diagnostics only: produce audit summary, do not touch redirects/ops beyond ensuring registries exist
        audit.append(_audit_record(
            severity=SEV_ADVISORY,
            code="NO_PLAN_PROVIDED",
            message="No plan provided; running diagnostics-only and emitting audit summary",
        ))
        report["plan_validated"] = True
    else:
        if not isinstance(plan, dict):
            audit.append(_audit_record(
                severity=SEV_HARD,
                code="PLAN_NOT_OBJECT",
                message="Plan must be a JSON object",
            ))
        else:
            ops_any = plan.get("operations", [])
            if not isinstance(ops_any, list):
                audit.append(_audit_record(
                    severity=SEV_HARD,
                    code="PLAN_OPERATIONS_NOT_LIST",
                    message="plan.operations must be an array",
                    path="$.operations",
                ))
            else:
                # Filter dict ops; record non-dicts as hard
                for i, o in enumerate(ops_any):
                    if not isinstance(o, dict):
                        audit.append(_audit_record(
                            severity=SEV_HARD,
                            code="PLAN_OPERATION_NOT_OBJECT",
                            message="Operation must be an object",
                            path=f"$.operations[{i}]",
                        ))
                    else:
                        ops_in_plan.append(o)

            policy_any = plan.get("policy", {})
            policy = policy_any if isinstance(policy_any, dict) else {}

            report["plan_validated"] = True

    # Policy knobs (defaults)
    allow_override_cross_jurisdiction = bool(policy.get("allow_override_cross_jurisdiction", False))
    allow_override_root_conflict = bool(policy.get("allow_override_root_conflict", False))
    min_events_for_auto_merge = int(policy.get("min_events_for_auto_merge", 0) or 0)

    # -----------------------------------------------------------------------
    # Operation application
    # -----------------------------------------------------------------------

    # Track redirect additions for metrics
    touched_sources: set[str] = set()

    def add_redirect_rule(
        entity_kind: str,
        from_id: str,
        to_id: str,
        *,
        jurisdiction_system_id: Optional[str] = None,
        temporal: Optional[Dict[str, Any]] = None,
        generated_by: str = "place_plan_applier",
        op_id: Optional[str] = None,
        note: Optional[str] = None,
    ) -> None:
        """Add (or idempotently keep) a redirect rule.

        Redirects are stored in:
        - root.place_version_redirects when entity_kind == "place_version"
        - root.place_redirects        when entity_kind == "place_id"

        This keeps chains separate and makes diagnostics easier ("place_version first").
        """
        nonlocal report

        if entity_kind not in ("place_id", "place_version"):
            audit("hard", f"Unknown entity_kind={entity_kind!r} for redirect", op_id=op_id)
            return

        redirects_map = place_version_redirects if entity_kind == "place_version" else place_redirects

        if not from_id or not isinstance(from_id, str):
            audit("hard", "redirect.from_id missing/invalid", op_id=op_id)
            return
        if not to_id or not isinstance(to_id, str):
            audit("hard", "redirect.to_id missing/invalid", op_id=op_id)
            return
        if from_id == to_id:
            audit("hard", f"self-redirect not allowed: {from_id!r} -> {to_id!r}", op_id=op_id)
            return

        rule: Dict[str, Any] = {"kind": entity_kind}
        if entity_kind == "place_version":
            rule["to_place_version_id"] = to_id
        else:
            rule["to_place_id"] = to_id

        js = (jurisdiction_system_id or "").strip()
        if js:
            rule["jurisdiction_system_id"] = js

        if isinstance(temporal, dict) and temporal:
            rule["temporal"] = temporal

        rule["generated"] = {
            "by": generated_by,
            "op_id": op_id,
            "note": note,
        }

        arr = redirects_map.get(from_id)
        if arr is None:
            arr = []
            redirects_map[from_id] = arr

        if not isinstance(arr, list):
            audit("hard", f"redirects[{from_id!r}] must be a list", op_id=op_id)
            return

        # Idempotency: only append if no existing rule with same target + js + temporal.
        def _target_id(r: Dict[str, Any]) -> Optional[str]:
            if entity_kind == "place_version":
                v = r.get("to_place_version_id")
            else:
                v = r.get("to_place_id")
            return v if isinstance(v, str) else None

        for existing in arr:
            if not isinstance(existing, dict):
                continue
            if existing.get("kind") != entity_kind:
                continue
            if _target_id(existing) != to_id:
                continue
            if (existing.get("jurisdiction_system_id") or None) != (rule.get("jurisdiction_system_id") or None):
                continue
            if (existing.get("temporal") or None) != (rule.get("temporal") or None):
                continue
            # Already present.
            return

        arr.append(rule)
        report["redirects_added"] += 1

    def classify_temporal_quality(temporal: Optional[Dict[str, Any]], op_id: str) -> None:
        # Advisory if open-ended temporal
        start, end, open_ended = _parse_temporal(temporal)
        if open_ended:
            audit.append(_audit_record(
                severity=SEV_ADVISORY,
                code="OPEN_ENDED_TEMPORAL",
                message="Operation temporal scope is open-ended; acceptable but may need future enrichment",
                op_id=op_id,
            ))
        else:
            # Soft if range is very wide (heuristic)
            if start is not None and end is not None and (end - start) > 200:
                audit.append(_audit_record(
                    severity=SEV_SOFT,
                    code="VERY_WIDE_TEMPORAL_RANGE",
                    message="Operation temporal range is very wide; consider narrowing scope",
                    op_id=op_id,
                    details={"start_year": start, "end_year": end},
                ))

    # Apply each operation
    for op in ops_in_plan:
        report["operations_seen"] += 1

        op_id = op.get("id")
        if not isinstance(op_id, str) or not op_id.strip():
            op_id = f"op_{report['operations_seen']:04d}"
            audit.append(_audit_record(
                severity=SEV_SOFT,
                code="OP_ID_MISSING",
                message="Operation missing id; synthesized one",
                op_id=op_id,
            ))

        kind = op.get("kind")
        if kind not in ("merge", "split", "supersede"):
            audit.append(_audit_record(
                severity=SEV_HARD,
                code="OP_KIND_INVALID",
                message=f"Operation kind must be merge/split/supersede, got {kind!r}",
                op_id=op_id,
            ))
            # Still record ledger entry as failed
            place_operations.append({
                "id": op_id,
                "kind": kind,
                "status": "failed",
                "applied_at": _utc_now_iso(),
                "dry_run": bool(dry_run),
                "error": "invalid kind",
                "raw": op if verbosity >= 3 else None,
            })
            report["operations_failed"] += 1
            continue

        entity_kind = op.get("entity_kind", "place_version")
        if entity_kind not in ("place_id", "place_version"):
            audit.append(_audit_record(
                severity=SEV_HARD,
                code="OP_ENTITY_KIND_INVALID",
                message=f"entity_kind must be place_id or place_version, got {entity_kind!r}",
                op_id=op_id,
            ))
            place_operations.append({
                "id": op_id,
                "kind": kind,
                "entity_kind": entity_kind,
                "status": "failed",
                "applied_at": _utc_now_iso(),
                "dry_run": bool(dry_run),
                "error": "invalid entity_kind",
            })
            report["operations_failed"] += 1
            continue

        override = bool(op.get("override", False))
        js = op.get("jurisdiction_system_id")
        temporal = op.get("temporal")
        classify_temporal_quality(temporal if isinstance(temporal, dict) else None, op_id)

        # Validate jurisdiction if provided
        if isinstance(js, str) and js.strip():
            if not jurisdiction_exists(js):
                audit.append(_audit_record(
                    severity=SEV_SOFT,
                    code="OP_JURISDICTION_UNKNOWN",
                    message=f"jurisdiction_system_id {js!r} not present in root.jurisdiction_systems",
                    op_id=op_id,
                ))

        # Normalize from/to ids
        from_ids: List[str] = []
        to_id: Optional[str] = None
        to_ids: List[str] = []

        if kind in ("merge",):
            from_any = op.get("from_ids")
            if isinstance(from_any, list):
                from_ids = [x for x in from_any if isinstance(x, str) and x.strip()]
            to_any = op.get("to_id")
            to_id = to_any if isinstance(to_any, str) and to_any.strip() else None

            if len(from_ids) < 2:
                audit.append(_audit_record(
                    severity=SEV_HARD,
                    code="MERGE_NEEDS_2_FROM",
                    message="merge requires from_ids with at least 2 ids",
                    op_id=op_id,
                ))
            if not to_id:
                audit.append(_audit_record(
                    severity=SEV_HARD,
                    code="MERGE_NEEDS_TO",
                    message="merge requires to_id",
                    op_id=op_id,
                ))

        elif kind in ("supersede",):
            from_any = op.get("from_id")
            if isinstance(from_any, str) and from_any.strip():
                from_ids = [from_any.strip()]
            to_any = op.get("to_id")
            to_id = to_any if isinstance(to_any, str) and to_any.strip() else None

            if len(from_ids) != 1:
                audit.append(_audit_record(
                    severity=SEV_HARD,
                    code="SUPERSEDE_NEEDS_FROM",
                    message="supersede requires from_id string",
                    op_id=op_id,
                ))
            if not to_id:
                audit.append(_audit_record(
                    severity=SEV_HARD,
                    code="SUPERSEDE_NEEDS_TO",
                    message="supersede requires to_id string",
                    op_id=op_id,
                ))

        elif kind in ("split",):
            from_any = op.get("from_id")
            if isinstance(from_any, str) and from_any.strip():
                from_ids = [from_any.strip()]
            to_any = op.get("to_ids")
            if isinstance(to_any, list):
                to_ids = [x for x in to_any if isinstance(x, str) and x.strip()]

            if len(from_ids) != 1:
                audit.append(_audit_record(
                    severity=SEV_HARD,
                    code="SPLIT_NEEDS_FROM",
                    message="split requires from_id string",
                    op_id=op_id,
                ))
            # to_ids may be empty for "draft split"; advisory not hard
            if not to_ids:
                audit.append(_audit_record(
                    severity=SEV_ADVISORY,
                    code="SPLIT_NO_TO_IDS",
                    message="split has no to_ids; recorded but no redirects can be produced",
                    op_id=op_id,
                ))

        # Existence checks
        def exists_check(eid: str) -> bool:
            return place_id_exists(eid) if entity_kind == "place_id" else place_version_exists(eid)

        if to_id:
            if not exists_check(to_id):
                audit.append(_audit_record(
                    severity=SEV_HARD,
                    code="TO_ID_NOT_FOUND",
                    message=f"to_id {to_id!r} not found in export registry for entity_kind={entity_kind}",
                    op_id=op_id,
                ))

        for fid in from_ids:
            if not exists_check(fid):
                audit.append(_audit_record(
                    severity=SEV_HARD,
                    code="FROM_ID_NOT_FOUND",
                    message=f"from_id {fid!r} not found in export registry for entity_kind={entity_kind}",
                    op_id=op_id,
                ))

        for tid in to_ids:
            if not exists_check(tid):
                audit.append(_audit_record(
                    severity=SEV_SOFT if kind == "split" else SEV_HARD,
                    code="TO_ID_NOT_FOUND",
                    message=f"to_id {tid!r} not found in export registry for entity_kind={entity_kind}",
                    op_id=op_id,
                ))

        # Root conflict check (heuristic for place_version only):
        # - If merging place_versions that point to different place_id, that is a "root conflict".
        # - Allowed only if override and policy allows.
        if entity_kind == "place_version" and kind in ("merge", "supersede"):
            # collect place_id roots
            roots: List[str] = []
            for fid in from_ids:
                pv = place_versions.get(fid)
                if isinstance(pv, dict) and isinstance(pv.get("place_id"), str):
                    roots.append(pv["place_id"])
            if to_id:
                pv = place_versions.get(to_id)
                if isinstance(pv, dict) and isinstance(pv.get("place_id"), str):
                    roots.append(pv["place_id"])

            if roots:
                uniq = sorted(set(roots))
                if len(uniq) > 1:
                    if not override or not allow_override_root_conflict:
                        audit.append(_audit_record(
                            severity=SEV_HARD,
                            code="ROOT_CONFLICT",
                            message="place_version operation crosses multiple underlying place_id roots; require override + policy allow_override_root_conflict",
                            op_id=op_id,
                            details={"roots": uniq},
                        ))
                    else:
                        audit.append(_audit_record(
                            severity=SEV_SOFT,
                            code="ROOT_CONFLICT_OVERRIDDEN",
                            message="Root conflict overridden by plan; ensure downstream applier rewrites are carefully audited",
                            op_id=op_id,
                            details={"roots": uniq},
                        ))

        # Cross-jurisdiction conflict check (heuristic for place_version only):
        if entity_kind == "place_version" and kind in ("merge", "supersede"):
            js_roots: List[str] = []
            for fid in from_ids:
                pv = place_versions.get(fid)
                if isinstance(pv, dict) and isinstance(pv.get("jurisdiction_system_id"), str):
                    js_roots.append(pv["jurisdiction_system_id"])
            if to_id:
                pv = place_versions.get(to_id)
                if isinstance(pv, dict) and isinstance(pv.get("jurisdiction_system_id"), str):
                    js_roots.append(pv["jurisdiction_system_id"])
            uniq_js = sorted(set(js_roots))
            if len(uniq_js) > 1:
                if not override or not allow_override_cross_jurisdiction:
                    audit.append(_audit_record(
                        severity=SEV_HARD,
                        code="CROSS_JURISDICTION_MERGE",
                        message="place_version operation spans multiple jurisdiction_system_id values; require override + policy allow_override_cross_jurisdiction",
                        op_id=op_id,
                        details={"jurisdictions": uniq_js},
                    ))
                else:
                    audit.append(_audit_record(
                        severity=SEV_SOFT,
                        code="CROSS_JURISDICTION_OVERRIDDEN",
                        message="Cross-jurisdiction merge overridden; ensure this is intentional",
                        op_id=op_id,
                        details={"jurisdictions": uniq_js},
                    ))

        # Decide operation status from audit (hard errors tied to this op)
        op_hard = [
            a for a in audit
            if a.get("op_id") == op_id and a.get("severity") == SEV_HARD
        ]
        if op_hard:
            place_operations.append({
                "id": op_id,
                "kind": kind,
                "entity_kind": entity_kind,
                "jurisdiction_system_id": js if isinstance(js, str) else None,
                "temporal": temporal if isinstance(temporal, dict) else None,
                "override": bool(override),
                "status": "failed",
                "applied_at": _utc_now_iso(),
                "dry_run": bool(dry_run),
                "error_count": len(op_hard),
                "notes": op.get("notes"),
            })
            report["operations_failed"] += 1
            continue

        # Apply (or dry-run)
        if kind in ("merge", "supersede") and to_id:
            # Evidence threshold advisory (optional): if op supplies evidence.events, compare to policy
            ev_count = 0
            ev = op.get("evidence")
            if isinstance(ev, dict) and isinstance(ev.get("events"), int):
                ev_count = int(ev["events"])
            if min_events_for_auto_merge > 0 and ev_count and ev_count < min_events_for_auto_merge and not override:
                audit.append(_audit_record(
                    severity=SEV_SOFT,
                    code="LOW_EVIDENCE_MERGE",
                    message="Merge evidence.events below policy threshold; consider override or more evidence",
                    op_id=op_id,
                    details={"events": ev_count, "min_events_for_auto_merge": min_events_for_auto_merge},
                ))

            if not dry_run:
                for fid in from_ids:
                    add_redirect_rule(
                        from_id=fid,
                        to_id=to_id,
                        entity_kind=entity_kind,
                        op_id=op_id,
                        jurisdiction_system_id=js if isinstance(js, str) else None,
                        temporal=temporal if isinstance(temporal, dict) else None,
                        generated_rule=f"{kind}_redirect",
                    )

            place_operations.append({
                "id": op_id,
                "kind": kind,
                "entity_kind": entity_kind,
                "from_ids": from_ids,
                "to_id": to_id,
                "jurisdiction_system_id": js if isinstance(js, str) else None,
                "temporal": temporal if isinstance(temporal, dict) else None,
                "override": bool(override),
                "status": "applied" if not dry_run else "dry_run",
                "applied_at": _utc_now_iso(),
                "dry_run": bool(dry_run),
                "notes": op.get("notes"),
                "evidence": op.get("evidence") if isinstance(op.get("evidence"), dict) else None,
            })
            report["operations_applied"] += 1

        elif kind == "split":
            # No redirects produced by default.
            if not dry_run:
                pass

            place_operations.append({
                "id": op_id,
                "kind": kind,
                "entity_kind": entity_kind,
                "from_id": from_ids[0] if from_ids else None,
                "to_ids": to_ids,
                "jurisdiction_system_id": js if isinstance(js, str) else None,
                "temporal": temporal if isinstance(temporal, dict) else None,
                "override": bool(override),
                "status": "recorded" if not dry_run else "dry_run",
                "applied_at": _utc_now_iso(),
                "dry_run": bool(dry_run),
                "notes": op.get("notes"),
            })
            report["operations_applied"] += 1

            audit.append(_audit_record(
                severity=SEV_ADVISORY,
                code="SPLIT_REQUIRES_ALLOCATION",
                message="split recorded but no redirects created; requires allocation rules to deterministically reassign references",
                op_id=op_id,
            ))

        else:
            # Should not happen; but be safe
            place_operations.append({
                "id": op_id,
                "kind": kind,
                "entity_kind": entity_kind,
                "status": "failed",
                "applied_at": _utc_now_iso(),
                "dry_run": bool(dry_run),
                "error": "unhandled operation shape",
            })
            report["operations_failed"] += 1
            audit.append(_audit_record(
                severity=SEV_HARD,
                code="UNHANDLED_OPERATION",
                message="Unhandled operation shape; internal error",
                op_id=op_id,
            ))

    report["redirect_sources_touched"] = len(touched_sources)

    # -----------------------------------------------------------------------
    # Finalize audit + summary into export root
    # -----------------------------------------------------------------------
    # Merge applier audit into root.place_audit
    for a in audit:
        if isinstance(a, dict):
            place_audit.append(a)

    summary_counts = _audit_counts([x for x in place_audit if isinstance(x, dict)])
    root["place_audit_summary"] = {
        "hard": summary_counts[SEV_HARD],
        "soft": summary_counts[SEV_SOFT],
        "advisory": summary_counts[SEV_ADVISORY],
        "total": summary_counts["total"],
        "generated": {
            "by": "place_plan_applier",
            "timestamp": _utc_now_iso(),
        },
    }

    report["audit_summary"] = dict(root["place_audit_summary"])

    # -----------------------------------------------------------------------
    # Fail policy
    # -----------------------------------------------------------------------
    hard = summary_counts[SEV_HARD]
    soft = summary_counts[SEV_SOFT]
    advisory = summary_counts[SEV_ADVISORY]

    should_fail = False
    if hard > 0:
        should_fail = True
    if fail_on_soft and soft > 0:
        should_fail = True
    if fail_on_advisory and advisory > 0:
        should_fail = True

    report["should_fail"] = should_fail

    
    # -------------------------------------------------------------------------
    # Diagnostics: full redirect chains (place_version first)
    # -------------------------------------------------------------------------
    if verbosity >= 2:
        def _build_chains(redirects_map: Dict[str, Any], *, kind: str, max_steps: int, limit: int) -> Dict[str, Any]:
            chains: List[Dict[str, Any]] = []
            longest = 0
            cycles = 0
            branching = 0

            # Pre-normalize adjacency: from -> list(to)
            adj: Dict[str, List[str]] = {}
            for src, arr in (redirects_map or {}).items():
                if not isinstance(src, str) or not src:
                    continue
                if not isinstance(arr, list):
                    continue
                outs: List[str] = []
                for r in arr:
                    if not isinstance(r, dict):
                        continue
                    if r.get("kind") != kind:
                        continue
                    tgt = r.get("to_place_version_id") if kind == "place_version" else r.get("to_place_id")
                    if isinstance(tgt, str) and tgt:
                        outs.append(tgt)
                if outs:
                    adj[src] = outs

            for src, outs in adj.items():
                if len(outs) > 1:
                    branching += 1

            # Build chains for sources (bounded and deterministic: follow first target if multiple)
            for src in sorted(adj.keys()):
                if len(chains) >= limit:
                    break
                seen: Set[str] = set()
                chain: List[str] = [src]
                cur = src
                step = 0
                cycle = False

                while step < max_steps:
                    if cur in seen:
                        cycle = True
                        cycles += 1
                        break
                    seen.add(cur)
                    outs = adj.get(cur, [])
                    if not outs:
                        break
                    # Deterministic choice: first target lexicographically
                    nxt = sorted(outs)[0]
                    chain.append(nxt)
                    cur = nxt
                    step += 1

                longest = max(longest, len(chain) - 1)
                chains.append({
                    "from_id": src,
                    "chain": chain,
                    "terminal_id": cur,
                    "length": len(chain) - 1,
                    "cycle_detected": cycle,
                    "branching_out_degree": len(adj.get(src, [])),
                })

            return {
                "kind": kind,
                "sources": len(adj),
                "branching_sources": branching,
                "cycles_detected": cycles,
                "longest_chain": longest,
                "chains": chains,
                "max_steps": max_steps,
                "limit": limit,
            }

        diag: Dict[str, Any] = report.setdefault("diagnostics", {})
        max_steps = 50
        limit = 50 if verbosity == 2 else 500
        diag["place_version_redirect_chains"] = _build_chains(place_version_redirects, kind="place_version", max_steps=max_steps, limit=limit)
        diag["place_id_redirect_chains"] = _build_chains(place_redirects, kind="place_id", max_steps=max_steps, limit=limit)

    return root, report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="C.24.9 – Place plan applier (audit + redirects + ledger)")

    p.add_argument("-i", "--input", required=True, help="Input JSON (C.24.7 export, e.g. outputs/export_c24_7.json)")
    p.add_argument("-o", "--output", required=True, help="Output JSON (C.24.9 export, e.g. outputs/export_c24_9.json)")
    p.add_argument("-p", "--plan", default=None, help="Optional plan JSON (C.24.9 place plan)")

    p.add_argument("--dry-run", action="store_true", help="Record operations + audit but do not modify place_redirects")
    p.add_argument("--fail-on-soft", action="store_true", help="Exit non-zero if any soft findings exist")
    p.add_argument("--fail-on-advisory", action="store_true", help="Exit non-zero if any advisory findings exist")

    p.add_argument("--verbosity", type=int, default=1, choices=[0, 1, 2, 3], help="0..3 (higher includes more details in report)")
    p.add_argument("--report", default=None, help="Write applier report JSON to this path")

    # Optional schema validation if jsonschema is installed
    p.add_argument("--schema-export", default=None, help="Optional schema path to validate output export")
    p.add_argument("--schema-plan", default=None, help="Optional schema path to validate plan")

    p.add_argument("--debug", action="store_true", help="Enable debug logging")
    return p


def main(argv: Optional[List[str]] = None) -> None:
    args = build_arg_parser().parse_args(argv)

    if args.debug:
        log.setLevel("DEBUG")

    log.info("Loading input export: %s", args.input)
    with open(args.input, "r", encoding="utf-8") as f:
        export_root = json.load(f)

    plan_obj: Optional[Dict[str, Any]] = None
    if args.plan:
        log.info("Loading plan: %s", args.plan)
        with open(args.plan, "r", encoding="utf-8") as f:
            plan_any = json.load(f)
        plan_obj = plan_any if isinstance(plan_any, dict) else None

        if args.schema_plan:
            errs = _jsonschema_validate_if_available(plan_any, args.schema_plan)
            if errs:
                log.error("Plan schema validation failed with %d error(s)", len(errs))
                for e in errs[:50]:
                    log.error(" - %s", e)
                raise SystemExit(2)

    # Apply
    out_root, report = apply_place_plan(
        export_root,
        plan_obj,
        dry_run=bool(args.dry_run),
        verbosity=int(args.verbosity),
        fail_on_soft=bool(args.fail_on_soft),
        fail_on_advisory=bool(args.fail_on_advisory),
    )

    # Write output
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(out_root, f, ensure_ascii=False, indent=2)

    # Optional validate output export
    if args.schema_export:
        errs = _jsonschema_validate_if_available(out_root, args.schema_export)
        if errs:
            log.error("Output export schema validation failed with %d error(s)", len(errs))
            for e in errs[:50]:
                log.error(" - %s", e)
            raise SystemExit(2)

    # Optional report
    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

    summ = report.get("audit_summary") or {}
    hard = int(summ.get("hard", 0) or 0)
    soft = int(summ.get("soft", 0) or 0)
    adv = int(summ.get("advisory", 0) or 0)
    log.info("C.24.9 applier complete: hard=%d soft=%d advisory=%d dry_run=%s", hard, soft, adv, bool(args.dry_run))

    if report.get("should_fail"):
        print("[ERROR] C.24.9 applier failed policy thresholds")
        raise SystemExit(1)

    print(f"[OK] C.24.9 export written to: {args.output}")
    if args.report:
        print(f"[OK] C.24.9 applier report written to: {args.report}")


if __name__ == "__main__":
    main()
