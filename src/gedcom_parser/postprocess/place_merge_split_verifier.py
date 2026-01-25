#!/usr/bin/env python3
"""
place_merge_split_verifier.py

C.24.8 – Place Merge / Split Verifier
Policy-driven safety validation (HARD / SOFT / ADVISORY)

This verifier is designed to validate:
- root.place_redirects (redirect DAG; no cycles; no self loops; bounded depth)
- root.place_operations (merge/split/supersede ledger integrity)
- cross-references to root.places and root.jurisdiction_systems
- redirect ambiguity across jurisdiction + temporal scopes
- event determinism under redirects
- optional external merge/split plan validation (draft plans for human review)

Key principles
--------------
- Read-only: NEVER mutates export JSON.
- Deterministic: same input => same findings.
- Explainable: each finding includes rule_id, severity, message, and pointer.
- Policy-driven: can treat some findings as SOFT/ADVISORY or elevate to HARD.

Typical usage
-------------
Diagnostics only (no plan):
    python -m gedcom_parser.postprocess.place_merge_split_verifier \
      -i outputs/export_c24_7.json \
      --report outputs/place_merge_split_report.json

With a plan:
    python -m gedcom_parser.postprocess.place_merge_split_verifier \
      -i outputs/export_c24_7.json \
      --plan merge_plan.json \
      --report outputs/place_merge_split_plan_report.json
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from gedcom_parser.logger import get_logger

log = get_logger("place_merge_split_verifier")


# =============================================================================
# Severity + Issue model
# =============================================================================

class Severity(str, Enum):
    HARD = "hard"
    SOFT = "soft"
    ADVISORY = "advisory"


@dataclass
class Issue:
    severity: Severity
    rule_id: str
    message: str
    pointer: str = "$"
    context: Dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "severity": self.severity.value,
            "rule_id": self.rule_id,
            "message": self.message,
            "pointer": self.pointer,
        }
        if self.context:
            out["context"] = self.context
        return out


# =============================================================================
# Policy model
# =============================================================================

@dataclass
class Policy:
    # If True, any SOFT issue causes failure exit.
    fail_on_soft_warnings: bool = False

    # If True, any ADVISORY issue causes failure exit.
    fail_on_advisory: bool = False

    # Redirect chain depth safety bound.
    max_redirect_chain: int = 25

    # If False, overlapping redirect scopes that map to different targets is not allowed.
    allow_ambiguous_redirects: bool = False

    # If False, merging across jurisdiction scopes is disallowed unless override is True AND allow_override_cross_jurisdiction is True.
    allow_override_cross_jurisdiction: bool = False

    # If False, root conflicts (cross-root merges) are disallowed unless override is True AND allow_override_root_conflict is True.
    allow_override_root_conflict: bool = False

    # Minimum evidence threshold for auto-merge suggestions (informational).
    min_events_for_auto_merge: int = 10

    # Enable scanning events for determinism issues under redirects.
    check_events_against_redirects: bool = True

    # Whether to treat missing optional registries as advisory vs hard.
    require_place_operations_registry: bool = False
    require_place_redirects_registry: bool = False

    @staticmethod
    def from_plan(plan: Dict[str, Any]) -> "Policy":
        p = Policy()
        raw = plan.get("policy")
        if isinstance(raw, dict):
            p.fail_on_soft_warnings = bool(raw.get("fail_on_soft_warnings", p.fail_on_soft_warnings))
            p.fail_on_advisory = bool(raw.get("fail_on_advisory", p.fail_on_advisory))
            if isinstance(raw.get("max_redirect_chain"), int):
                p.max_redirect_chain = int(raw["max_redirect_chain"])
            p.allow_ambiguous_redirects = bool(raw.get("allow_ambiguous_redirects", p.allow_ambiguous_redirects))
            p.allow_override_cross_jurisdiction = bool(
                raw.get("allow_override_cross_jurisdiction", p.allow_override_cross_jurisdiction)
            )
            p.allow_override_root_conflict = bool(raw.get("allow_override_root_conflict", p.allow_override_root_conflict))
            if isinstance(raw.get("min_events_for_auto_merge"), int):
                p.min_events_for_auto_merge = int(raw["min_events_for_auto_merge"])
            if "check_events_against_redirects" in raw:
                p.check_events_against_redirects = bool(raw["check_events_against_redirects"])
            if "require_place_operations_registry" in raw:
                p.require_place_operations_registry = bool(raw["require_place_operations_registry"])
            if "require_place_redirects_registry" in raw:
                p.require_place_redirects_registry = bool(raw["require_place_redirects_registry"])
        return p


# =============================================================================
# Redirect scope utilities
# =============================================================================

@dataclass(frozen=True)
class RedirectScope:
    js: Optional[str]                 # jurisdiction_system_id or None (global)
    start: Optional[int]              # inclusive
    end: Optional[int]                # inclusive

    def overlaps(self, other: "RedirectScope") -> bool:
        if (self.js or None) != (other.js or None):
            return False

        lo_a = self.start if self.start is not None else -10**18
        hi_a = self.end if self.end is not None else 10**18
        lo_b = other.start if other.start is not None else -10**18
        hi_b = other.end if other.end is not None else 10**18

        return not (hi_a < lo_b or hi_b < lo_a)

    def to_json(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"jurisdiction_system_id": self.js}
        if self.start is not None:
            out["start_year"] = self.start
        if self.end is not None:
            out["end_year"] = self.end
        if self.start is None and self.end is None:
            out["open_ended"] = True
        return out


def _parse_temporal_scope(t: Any) -> Tuple[Optional[int], Optional[int]]:
    """
    Supports:
      temporal: {bucket:"year", year: 1912}
      temporal: {bucket:"year", start_year: 1800, end_year: 1820}
      temporal: {bucket:"year", open_ended:true}
      temporal: {bucket:"year"}  -> treated as open ended
    """
    if not isinstance(t, dict):
        return (None, None)

    sy = t.get("start_year")
    ey = t.get("end_year")
    if isinstance(sy, int) or isinstance(ey, int):
        return (sy if isinstance(sy, int) else None, ey if isinstance(ey, int) else None)

    y = t.get("year")
    if isinstance(y, int):
        return (int(y), int(y))

    if t.get("open_ended") is True:
        return (None, None)

    # If bucket present but no year/range: interpret open-ended
    if isinstance(t.get("bucket"), str):
        return (None, None)

    return (None, None)


def _redirect_scope(r: Dict[str, Any]) -> RedirectScope:
    js = r.get("jurisdiction_system_id")
    js_id = js if isinstance(js, str) and js.strip() else None
    start, end = _parse_temporal_scope(r.get("temporal"))
    return RedirectScope(js=js_id, start=start, end=end)


# =============================================================================
# Export inspection utilities
# =============================================================================

def _iter_event_dicts(root: Dict[str, Any]) -> Iterable[Tuple[str, str, int, Dict[str, Any]]]:
    """
    Yields (group, record_ptr, event_index, event_dict)
    """
    for group in ("individuals", "families"):
        g = root.get(group, {})
        if not isinstance(g, dict):
            continue
        for rec_ptr, rec in g.items():
            if not isinstance(rec, dict):
                continue
            evs = rec.get("events", [])
            if not isinstance(evs, list):
                continue
            for idx, ev in enumerate(evs):
                if isinstance(ev, dict):
                    yield (group, str(rec_ptr), idx, ev)


def _safe_len(x: Any) -> int:
    if isinstance(x, dict) or isinstance(x, list) or isinstance(x, str):
        return len(x)
    return 0


# =============================================================================
# Plan model (optional external plan)
# =============================================================================

@dataclass
class MergeOpPlan:
    id: str
    merge_kind: str  # "place_version" or "place_id"
    override: bool = False
    notes: str = ""
    from_place_ids: List[str] = field(default_factory=list)
    to_place_id: Optional[str] = None
    from_place_version_ids: List[str] = field(default_factory=list)
    to_place_version_id: Optional[str] = None
    jurisdiction_system_id: Optional[str] = None
    temporal: Optional[Dict[str, Any]] = None


@dataclass
class SplitOpPlan:
    id: str
    split_kind: str  # "place_version" or "place_id"
    override: bool = False
    notes: str = ""
    from_place_id: Optional[str] = None
    to_place_ids: List[str] = field(default_factory=list)
    from_place_version_id: Optional[str] = None
    to_place_version_ids: List[str] = field(default_factory=list)
    jurisdiction_system_id: Optional[str] = None
    temporal: Optional[Dict[str, Any]] = None


def _load_plan(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _parse_merge_plan(item: Any, idx: int, issues: List[Issue]) -> Optional[MergeOpPlan]:
    ptr = f"$.plan.merges[{idx}]"
    if not isinstance(item, dict):
        issues.append(Issue(Severity.HARD, "plan.merge.not_object", "Merge entry must be an object", ptr))
        return None

    op_id = item.get("id")
    kind = item.get("merge_kind")
    if not isinstance(op_id, str) or not op_id.strip():
        issues.append(Issue(Severity.HARD, "plan.merge.missing_id", "Merge entry missing/invalid id", ptr))
        return None
    if kind not in ("place_version", "place_id"):
        issues.append(Issue(Severity.HARD, "plan.merge.invalid_kind", f"Invalid merge_kind={kind!r}", ptr, {"id": op_id}))
        return None

    m = MergeOpPlan(id=op_id, merge_kind=kind, override=bool(item.get("override", False)))
    if isinstance(item.get("notes"), str):
        m.notes = item["notes"]

    js = item.get("jurisdiction_system_id")
    if isinstance(js, str) and js.strip():
        m.jurisdiction_system_id = js.strip()

    temporal = item.get("temporal")
    if isinstance(temporal, dict):
        m.temporal = temporal

    if kind == "place_id":
        fps = item.get("from_place_ids")
        tp = item.get("to_place_id")
        if not (isinstance(fps, list) and all(isinstance(x, str) and x.strip() for x in fps)):
            issues.append(Issue(Severity.HARD, "plan.merge.place_id.missing_from", "from_place_ids[] required (strings)", ptr, {"id": op_id}))
            return None
        m.from_place_ids = [x.strip() for x in fps]
        if tp is not None:
            if not (isinstance(tp, str) and tp.strip()):
                issues.append(Issue(Severity.HARD, "plan.merge.place_id.invalid_to", "to_place_id must be a string if provided", ptr, {"id": op_id}))
                return None
            m.to_place_id = tp.strip()

    if kind == "place_version":
        fps = item.get("from_place_version_ids")
        tp = item.get("to_place_version_id")
        if not (isinstance(fps, list) and all(isinstance(x, str) and x.strip() for x in fps)):
            issues.append(Issue(Severity.HARD, "plan.merge.place_version.missing_from", "from_place_version_ids[] required (strings)", ptr, {"id": op_id}))
            return None
        m.from_place_version_ids = [x.strip() for x in fps]
        if tp is not None:
            if not (isinstance(tp, str) and tp.strip()):
                issues.append(Issue(Severity.HARD, "plan.merge.place_version.invalid_to", "to_place_version_id must be a string if provided", ptr, {"id": op_id}))
                return None
            m.to_place_version_id = tp.strip()

    return m


def _parse_split_plan(item: Any, idx: int, issues: List[Issue]) -> Optional[SplitOpPlan]:
    ptr = f"$.plan.splits[{idx}]"
    if not isinstance(item, dict):
        issues.append(Issue(Severity.HARD, "plan.split.not_object", "Split entry must be an object", ptr))
        return None

    op_id = item.get("id")
    kind = item.get("split_kind")
    if not isinstance(op_id, str) or not op_id.strip():
        issues.append(Issue(Severity.HARD, "plan.split.missing_id", "Split entry missing/invalid id", ptr))
        return None
    if kind not in ("place_version", "place_id"):
        issues.append(Issue(Severity.HARD, "plan.split.invalid_kind", f"Invalid split_kind={kind!r}", ptr, {"id": op_id}))
        return None

    s = SplitOpPlan(id=op_id, split_kind=kind, override=bool(item.get("override", False)))
    if isinstance(item.get("notes"), str):
        s.notes = item["notes"]

    js = item.get("jurisdiction_system_id")
    if isinstance(js, str) and js.strip():
        s.jurisdiction_system_id = js.strip()

    temporal = item.get("temporal")
    if isinstance(temporal, dict):
        s.temporal = temporal

    if kind == "place_id":
        fp = item.get("from_place_id")
        tps = item.get("to_place_ids")
        if not (isinstance(fp, str) and fp.strip()):
            issues.append(Issue(Severity.HARD, "plan.split.place_id.missing_from", "from_place_id required", ptr, {"id": op_id}))
            return None
        s.from_place_id = fp.strip()
        if tps is not None:
            if not (isinstance(tps, list) and all(isinstance(x, str) and x.strip() for x in tps)):
                issues.append(Issue(Severity.HARD, "plan.split.place_id.invalid_to", "to_place_ids must be list of strings if provided", ptr, {"id": op_id}))
                return None
            s.to_place_ids = [x.strip() for x in tps]

    if kind == "place_version":
        fp = item.get("from_place_version_id")
        tps = item.get("to_place_version_ids")
        if not (isinstance(fp, str) and fp.strip()):
            issues.append(Issue(Severity.HARD, "plan.split.place_version.missing_from", "from_place_version_id required", ptr, {"id": op_id}))
            return None
        s.from_place_version_id = fp.strip()
        if tps is not None:
            if not (isinstance(tps, list) and all(isinstance(x, str) and x.strip() for x in tps)):
                issues.append(Issue(Severity.HARD, "plan.split.place_version.invalid_to", "to_place_version_ids must be list of strings if provided", ptr, {"id": op_id}))
                return None
            s.to_place_version_ids = [x.strip() for x in tps]

    return s


# =============================================================================
# Core Verifier
# =============================================================================

@dataclass
class VerifyMetrics:
    redirects_sources: int = 0
    redirects_entries: int = 0
    operations: int = 0
    cycles: int = 0
    ambiguous_redirect_sets: int = 0
    missing_place_refs: int = 0
    missing_jurisdiction_refs: int = 0
    event_ambiguities: int = 0
    chain_too_deep: int = 0
    plan_merges: int = 0
    plan_splits: int = 0
    plan_errors: int = 0

    def to_json(self) -> Dict[str, Any]:
        return {
            "redirects_sources": self.redirects_sources,
            "redirects_entries": self.redirects_entries,
            "operations": self.operations,
            "cycles": self.cycles,
            "ambiguous_redirect_sets": self.ambiguous_redirect_sets,
            "missing_place_refs": self.missing_place_refs,
            "missing_jurisdiction_refs": self.missing_jurisdiction_refs,
            "event_ambiguities": self.event_ambiguities,
            "chain_too_deep": self.chain_too_deep,
            "plan_merges": self.plan_merges,
            "plan_splits": self.plan_splits,
            "plan_errors": self.plan_errors,
        }


def verify_merge_split(
    root: Dict[str, Any],
    *,
    policy: Policy,
    plan: Optional[Dict[str, Any]] = None,
) -> Tuple[VerifyMetrics, List[Issue]]:
    """
    Validate C.24.8 merge/split semantics registries and optional plan.
    Returns (metrics, issues).
    """
    metrics = VerifyMetrics()
    issues: List[Issue] = []

    # ---- basic root checks ----
    places = root.get("places")
    if not isinstance(places, dict):
        issues.append(Issue(Severity.HARD, "root.places.missing", "root.places missing or not an object", "$.places"))
        places = {}

    jurisdiction_systems = root.get("jurisdiction_systems")
    if jurisdiction_systems is None:
        # In C.24.7 this exists; treat missing as SOFT (unless you want to elevate later)
        issues.append(Issue(Severity.SOFT, "root.jurisdiction_systems.missing", "root.jurisdiction_systems missing", "$.jurisdiction_systems"))
        jurisdiction_systems = {}
    elif not isinstance(jurisdiction_systems, dict):
        issues.append(Issue(Severity.HARD, "root.jurisdiction_systems.invalid", "root.jurisdiction_systems must be an object", "$.jurisdiction_systems"))
        jurisdiction_systems = {}

    redirects = root.get("place_redirects")
    if redirects is None:
        if policy.require_place_redirects_registry:
            issues.append(Issue(Severity.HARD, "root.place_redirects.missing", "root.place_redirects missing", "$.place_redirects"))
        else:
            issues.append(Issue(Severity.ADVISORY, "root.place_redirects.missing", "root.place_redirects missing (ok for now)", "$.place_redirects"))
        redirects = {}
    elif not isinstance(redirects, dict):
        issues.append(Issue(Severity.HARD, "root.place_redirects.invalid", "root.place_redirects must be an object", "$.place_redirects"))
        redirects = {}

    ops = root.get("place_operations")
    if ops is None:
        if policy.require_place_operations_registry:
            issues.append(Issue(Severity.HARD, "root.place_operations.missing", "root.place_operations missing", "$.place_operations"))
        else:
            issues.append(Issue(Severity.ADVISORY, "root.place_operations.missing", "root.place_operations missing (ok for now)", "$.place_operations"))
        ops = []
    elif not isinstance(ops, list):
        issues.append(Issue(Severity.HARD, "root.place_operations.invalid", "root.place_operations must be an array", "$.place_operations"))
        ops = []

    def place_exists(pid: str) -> bool:
        return isinstance(pid, str) and pid in places

    def js_exists(js_id: str) -> bool:
        return isinstance(js_id, str) and js_id in jurisdiction_systems

    # =============================================================================
    # [A] Validate place_operations ledger (merge/split/supersede)
    # =============================================================================
    seen_op_ids: Set[str] = set()
    for i, op_any in enumerate(ops):
        metrics.operations += 1
        ptr = f"$.place_operations[{i}]"

        if not isinstance(op_any, dict):
            issues.append(Issue(Severity.HARD, "ops.entry.not_object", "place_operations entry must be an object", ptr))
            continue

        op_id = op_any.get("id")
        if not isinstance(op_id, str) or not op_id.strip():
            issues.append(Issue(Severity.HARD, "ops.missing_id", "place_operations entry missing/invalid id", ptr))
        else:
            if op_id in seen_op_ids:
                issues.append(Issue(Severity.HARD, "ops.duplicate_id", f"Duplicate place_operations id={op_id!r}", ptr, {"id": op_id}))
            seen_op_ids.add(op_id)

        kind = op_any.get("kind")
        if kind not in ("merge", "split", "supersede"):
            issues.append(Issue(Severity.HARD, "ops.invalid_kind", f"Invalid kind={kind!r}", ptr, {"kind": kind}))
            continue

        # jurisdiction optional but if present must exist
        js_id = op_any.get("jurisdiction_system_id")
        if isinstance(js_id, str) and js_id.strip():
            if not js_exists(js_id):
                metrics.missing_jurisdiction_refs += 1
                issues.append(Issue(Severity.HARD, "ops.missing_jurisdiction", f"jurisdiction_system_id={js_id!r} not found", ptr, {"jurisdiction_system_id": js_id}))

        # temporal is optional; if present must be dict
        temporal = op_any.get("temporal")
        if temporal is not None and not isinstance(temporal, dict):
            issues.append(Issue(Severity.SOFT, "ops.temporal.invalid", "temporal should be an object if present", ptr + ".temporal"))

        if kind == "merge":
            fps = op_any.get("from_place_ids")
            tp = op_any.get("to_place_id")
            if not (isinstance(fps, list) and all(isinstance(x, str) and x.strip() for x in fps)):
                issues.append(Issue(Severity.HARD, "ops.merge.missing_from", "merge requires from_place_ids[] of strings", ptr))
            if not (isinstance(tp, str) and tp.strip()):
                issues.append(Issue(Severity.HARD, "ops.merge.missing_to", "merge requires to_place_id string", ptr))

            if isinstance(fps, list):
                for pid in fps:
                    if isinstance(pid, str) and pid.strip() and not place_exists(pid):
                        metrics.missing_place_refs += 1
                        issues.append(Issue(Severity.HARD, "ops.merge.missing_place", f"from_place_id={pid!r} not found in root.places", ptr + ".from_place_ids", {"place_id": pid}))
            if isinstance(tp, str) and tp.strip() and not place_exists(tp):
                metrics.missing_place_refs += 1
                issues.append(Issue(Severity.HARD, "ops.merge.missing_place", f"to_place_id={tp!r} not found in root.places", ptr + ".to_place_id", {"place_id": tp}))

        elif kind == "split":
            fp = op_any.get("from_place_id")
            tps = op_any.get("to_place_ids")
            if not (isinstance(fp, str) and fp.strip()):
                issues.append(Issue(Severity.HARD, "ops.split.missing_from", "split requires from_place_id string", ptr))
            if not (isinstance(tps, list) and all(isinstance(x, str) and x.strip() for x in tps)):
                issues.append(Issue(Severity.HARD, "ops.split.missing_to", "split requires to_place_ids[] of strings", ptr))

            if isinstance(fp, str) and fp.strip() and not place_exists(fp):
                metrics.missing_place_refs += 1
                issues.append(Issue(Severity.HARD, "ops.split.missing_place", f"from_place_id={fp!r} not found in root.places", ptr + ".from_place_id", {"place_id": fp}))
            if isinstance(tps, list):
                for pid in tps:
                    if isinstance(pid, str) and pid.strip() and not place_exists(pid):
                        metrics.missing_place_refs += 1
                        issues.append(Issue(Severity.HARD, "ops.split.missing_place", f"to_place_id={pid!r} not found in root.places", ptr + ".to_place_ids", {"place_id": pid}))

        elif kind == "supersede":
            fp = op_any.get("from_place_id")
            tp = op_any.get("to_place_id")
            if not (isinstance(fp, str) and fp.strip()):
                issues.append(Issue(Severity.HARD, "ops.supersede.missing_from", "supersede requires from_place_id string", ptr))
            if not (isinstance(tp, str) and tp.strip()):
                issues.append(Issue(Severity.HARD, "ops.supersede.missing_to", "supersede requires to_place_id string", ptr))

            if isinstance(fp, str) and fp.strip() and not place_exists(fp):
                metrics.missing_place_refs += 1
                issues.append(Issue(Severity.HARD, "ops.supersede.missing_place", f"from_place_id={fp!r} not found in root.places", ptr + ".from_place_id", {"place_id": fp}))
            if isinstance(tp, str) and tp.strip() and not place_exists(tp):
                metrics.missing_place_refs += 1
                issues.append(Issue(Severity.HARD, "ops.supersede.missing_place", f"to_place_id={tp!r} not found in root.places", ptr + ".to_place_id", {"place_id": tp}))

    # =============================================================================
    # [B] Validate place_redirects (graph + scope ambiguity + cycles + depth)
    # =============================================================================
    graph: Dict[str, Set[str]] = {}
    scoped_index: Dict[Tuple[str, Optional[str]], List[Tuple[RedirectScope, str, str]]] = {}
    # key: (from_place_id, js) -> list[(scope, to_place_id, pointer)]

    for from_pid, arr in redirects.items():
        metrics.redirects_sources += 1
        if not isinstance(from_pid, str) or not from_pid.strip():
            issues.append(Issue(Severity.HARD, "redirects.key.invalid", "place_redirects key must be a non-empty string", "$.place_redirects"))
            continue

        src_ptr = f"$.place_redirects[{json.dumps(from_pid)}]"
        if not place_exists(from_pid):
            metrics.missing_place_refs += 1
            issues.append(Issue(Severity.HARD, "redirects.source.missing_place", f"from_place_id={from_pid!r} not found in root.places", src_ptr, {"place_id": from_pid}))

        if not isinstance(arr, list):
            issues.append(Issue(Severity.HARD, "redirects.value.not_array", f"place_redirects[{from_pid!r}] must be an array", src_ptr))
            continue

        for j, r_any in enumerate(arr):
            metrics.redirects_entries += 1
            ptr = f"{src_ptr}[{j}]"

            if not isinstance(r_any, dict):
                issues.append(Issue(Severity.HARD, "redirects.entry.not_object", "redirect entry must be an object", ptr))
                continue

            to_pid = r_any.get("to_place_id")
            if not isinstance(to_pid, str) or not to_pid.strip():
                issues.append(Issue(Severity.HARD, "redirects.missing_to", "redirect missing/invalid to_place_id", ptr + ".to_place_id"))
                continue

            if to_pid == from_pid:
                issues.append(Issue(Severity.HARD, "redirects.self_loop", "self-redirect is not allowed", ptr, {"place_id": from_pid}))

            if not place_exists(to_pid):
                metrics.missing_place_refs += 1
                issues.append(Issue(Severity.HARD, "redirects.target.missing_place", f"to_place_id={to_pid!r} not found in root.places", ptr + ".to_place_id", {"place_id": to_pid}))

            js_id = r_any.get("jurisdiction_system_id")
            js_norm = js_id.strip() if isinstance(js_id, str) and js_id.strip() else None
            if js_norm and not js_exists(js_norm):
                metrics.missing_jurisdiction_refs += 1
                issues.append(Issue(Severity.HARD, "redirects.missing_jurisdiction", f"jurisdiction_system_id={js_norm!r} not found", ptr + ".jurisdiction_system_id", {"jurisdiction_system_id": js_norm}))

            # Graph edge ignores scope for cycle detection; scope is handled separately.
            graph.setdefault(from_pid, set()).add(to_pid)

            scope = _redirect_scope(r_any)
            scoped_index.setdefault((from_pid, scope.js), []).append((scope, to_pid, ptr))

    # ---- scoped ambiguity check ----
    if not policy.allow_ambiguous_redirects:
        for (from_pid, js_id), items in scoped_index.items():
            n = len(items)
            for a in range(n):
                sa, toa, ptra = items[a]
                for b in range(a + 1, n):
                    sb, tob, ptrb = items[b]
                    if toa == tob:
                        continue
                    if sa.overlaps(sb):
                        metrics.ambiguous_redirect_sets += 1
                        issues.append(
                            Issue(
                                Severity.HARD,
                                "redirects.ambiguous",
                                "Overlapping redirect scopes point to different targets",
                                "$.place_redirects",
                                {
                                    "from_place_id": from_pid,
                                    "jurisdiction_system_id": js_id,
                                    "a": {"to_place_id": toa, "scope": sa.to_json(), "pointer": ptra},
                                    "b": {"to_place_id": tob, "scope": sb.to_json(), "pointer": ptrb},
                                },
                            )
                        )

    # ---- cycles (DFS) ----
    visiting: Set[str] = set()
    visited: Set[str] = set()

    def dfs(node: str, stack: List[str]) -> None:
        if node in visiting:
            metrics.cycles += 1
            cycle_path = " -> ".join(stack + [node])
            issues.append(Issue(Severity.HARD, "redirects.cycle", f"Redirect cycle detected: {cycle_path}", "$.place_redirects", {"cycle": stack + [node]}))
            return
        if node in visited:
            return
        visiting.add(node)
        for nxt in graph.get(node, set()):
            dfs(nxt, stack + [node])
        visiting.remove(node)
        visited.add(node)

    for src in list(graph.keys()):
        if src not in visited:
            dfs(src, [])

    # ---- chain depth enforcement (only deterministic single-target chains) ----
    def chain_len(start: str) -> int:
        seen: Set[str] = set()
        cur = start
        steps = 0
        while True:
            if cur in seen:
                return steps
            seen.add(cur)

            outs = list(graph.get(cur, set()))
            if not outs:
                return steps

            # If multiple outs, chain length is ill-defined; ambiguity should be caught separately.
            if len(outs) != 1:
                return steps

            cur = outs[0]
            steps += 1
            if steps > policy.max_redirect_chain:
                return steps

    for src in graph.keys():
        steps = chain_len(src)
        if steps > policy.max_redirect_chain:
            metrics.chain_too_deep += 1
            issues.append(
                Issue(
                    Severity.HARD,
                    "redirects.chain_too_deep",
                    f"Redirect chain too deep (>{policy.max_redirect_chain}) for {src!r}",
                    "$.place_redirects",
                    {"from_place_id": src, "length": steps, "max": policy.max_redirect_chain},
                )
            )

    # =============================================================================
    # [C] Event determinism under redirects
    # =============================================================================
    if policy.check_events_against_redirects and (not policy.allow_ambiguous_redirects):
        # scope-less ambiguity map: from -> set(to) where multiple to exist
        ambiguous_map: Dict[str, Set[str]] = {k: set(v) for k, v in graph.items() if len(v) > 1}
        if ambiguous_map:
            for group, rec_ptr, idx, ev in _iter_event_dicts(root):
                pid = ev.get("place_id")
                if isinstance(pid, str) and pid in ambiguous_map:
                    metrics.event_ambiguities += 1
                    issues.append(
                        Issue(
                            Severity.HARD,
                            "events.ambiguous_under_redirects",
                            "Event place_id has multiple redirect targets (non-deterministic)",
                            f"$.{group}[{json.dumps(rec_ptr)}].events[{idx}].place_id",
                            {"place_id": pid, "targets": sorted(list(ambiguous_map[pid]))},
                        )
                    )

    # =============================================================================
    # [D] Optional plan validation (merges/splits against C.24.7 registries)
    # =============================================================================
    place_versions = root.get("place_versions", {})
    if place_versions is None:
        place_versions = {}
    if not isinstance(place_versions, dict):
        issues.append(Issue(Severity.SOFT, "root.place_versions.invalid", "root.place_versions should be an object if present", "$.place_versions"))
        place_versions = {}

    def pv_exists(pv_id: str) -> bool:
        return isinstance(pv_id, str) and pv_id in place_versions

    def pv_record(pv_id: str) -> Optional[Dict[str, Any]]:
        v = place_versions.get(pv_id)
        return v if isinstance(v, dict) else None

    if plan is not None:
        # Parse plan, collect structural issues first.
        plan_issues: List[Issue] = []
        merges_raw = plan.get("merges", [])
        splits_raw = plan.get("splits", [])
        if merges_raw is None:
            merges_raw = []
        if splits_raw is None:
            splits_raw = []

        if not isinstance(merges_raw, list):
            plan_issues.append(Issue(Severity.HARD, "plan.merges.invalid", "plan.merges must be an array", "$.plan.merges"))
            merges_raw = []
        if not isinstance(splits_raw, list):
            plan_issues.append(Issue(Severity.HARD, "plan.splits.invalid", "plan.splits must be an array", "$.plan.splits"))
            splits_raw = []

        merges: List[MergeOpPlan] = []
        for i, it in enumerate(merges_raw):
            m = _parse_merge_plan(it, i, plan_issues)
            if m:
                merges.append(m)

        splits: List[SplitOpPlan] = []
        for i, it in enumerate(splits_raw):
            s = _parse_split_plan(it, i, plan_issues)
            if s:
                splits.append(s)

        # Apply policy override rules and referential integrity checks.
        # These checks are "plan correctness", not "export correctness".
        for m in merges:
            metrics.plan_merges += 1
            ptr = f"$.plan.merges[{json.dumps(m.id)}]"

            if m.merge_kind == "place_id":
                for pid in m.from_place_ids:
                    if not place_exists(pid):
                        metrics.plan_errors += 1
                        plan_issues.append(Issue(Severity.HARD, "plan.merge.missing_place", f"from_place_id={pid!r} not found", ptr, {"place_id": pid}))
                if m.to_place_id is not None and not place_exists(m.to_place_id):
                    metrics.plan_errors += 1
                    plan_issues.append(Issue(Severity.HARD, "plan.merge.missing_place", f"to_place_id={m.to_place_id!r} not found", ptr, {"place_id": m.to_place_id}))

                # Advisory: merging a single id is pointless
                if len(m.from_place_ids) < 2:
                    plan_issues.append(Issue(Severity.ADVISORY, "plan.merge.too_few_sources", "merge should include 2+ sources", ptr, {"count": len(m.from_place_ids)}))

            if m.merge_kind == "place_version":
                for pv in m.from_place_version_ids:
                    if not pv_exists(pv):
                        metrics.plan_errors += 1
                        plan_issues.append(Issue(Severity.HARD, "plan.merge.missing_place_version", f"from_place_version_id={pv!r} not found", ptr, {"place_version_id": pv}))
                if m.to_place_version_id is not None and not pv_exists(m.to_place_version_id):
                    metrics.plan_errors += 1
                    plan_issues.append(Issue(Severity.HARD, "plan.merge.missing_place_version", f"to_place_version_id={m.to_place_version_id!r} not found", ptr, {"place_version_id": m.to_place_version_id}))

                if len(m.from_place_version_ids) < 2:
                    plan_issues.append(Issue(Severity.ADVISORY, "plan.merge.too_few_sources", "merge should include 2+ sources", ptr, {"count": len(m.from_place_version_ids)}))

                # Cross-jurisdiction safety check
                # If more than one jurisdiction_system_id across sources and no override policy => HARD
                js_set: Set[str] = set()
                for pv_id in m.from_place_version_ids:
                    rec = pv_record(pv_id)
                    if rec and isinstance(rec.get("jurisdiction_system_id"), str):
                        js_set.add(rec["jurisdiction_system_id"])
                if len(js_set) > 1:
                    if not m.override or not policy.allow_override_cross_jurisdiction:
                        plan_issues.append(
                            Issue(
                                Severity.HARD,
                                "plan.merge.cross_jurisdiction",
                                "Merge crosses jurisdiction_system_id scopes (disallowed by policy)",
                                ptr,
                                {"jurisdictions": sorted(list(js_set)), "override": m.override, "policy_allow": policy.allow_override_cross_jurisdiction},
                            )
                        )
                    else:
                        plan_issues.append(
                            Issue(
                                Severity.SOFT,
                                "plan.merge.cross_jurisdiction.override",
                                "Merge crosses jurisdiction_system_id scopes but allowed via override policy",
                                ptr,
                                {"jurisdictions": sorted(list(js_set)), "override": True},
                            )
                        )

        for s in splits:
            metrics.plan_splits += 1
            ptr = f"$.plan.splits[{json.dumps(s.id)}]"

            if s.split_kind == "place_id":
                if s.from_place_id and not place_exists(s.from_place_id):
                    metrics.plan_errors += 1
                    plan_issues.append(Issue(Severity.HARD, "plan.split.missing_place", f"from_place_id={s.from_place_id!r} not found", ptr, {"place_id": s.from_place_id}))
                for pid in s.to_place_ids:
                    if not place_exists(pid):
                        metrics.plan_errors += 1
                        plan_issues.append(Issue(Severity.HARD, "plan.split.missing_place", f"to_place_id={pid!r} not found", ptr, {"place_id": pid}))

                if not s.to_place_ids:
                    plan_issues.append(Issue(Severity.ADVISORY, "plan.split.no_targets", "Split has no to_place_ids targets yet (draft ok)", ptr))

            if s.split_kind == "place_version":
                if s.from_place_version_id and not pv_exists(s.from_place_version_id):
                    metrics.plan_errors += 1
                    plan_issues.append(Issue(Severity.HARD, "plan.split.missing_place_version", f"from_place_version_id={s.from_place_version_id!r} not found", ptr, {"place_version_id": s.from_place_version_id}))
                for pv in s.to_place_version_ids:
                    if not pv_exists(pv):
                        metrics.plan_errors += 1
                        plan_issues.append(Issue(Severity.HARD, "plan.split.missing_place_version", f"to_place_version_id={pv!r} not found", ptr, {"place_version_id": pv}))

                if not s.to_place_version_ids:
                    plan_issues.append(Issue(Severity.ADVISORY, "plan.split.no_targets", "Split has no to_place_version_ids targets yet (draft ok)", ptr))

        # Add plan issues into global issue list with policy semantics
        issues.extend(plan_issues)

    return metrics, issues


# =============================================================================
# Report + exit rules
# =============================================================================

def _summarize_issues(issues: Sequence[Issue]) -> Dict[str, int]:
    out = {"hard": 0, "soft": 0, "advisory": 0}
    for it in issues:
        if it.severity == Severity.HARD:
            out["hard"] += 1
        elif it.severity == Severity.SOFT:
            out["soft"] += 1
        elif it.severity == Severity.ADVISORY:
            out["advisory"] += 1
    return out


def _should_fail(issues: Sequence[Issue], policy: Policy) -> bool:
    counts = _summarize_issues(issues)
    if counts["hard"] > 0:
        return True
    if policy.fail_on_soft_warnings and counts["soft"] > 0:
        return True
    if policy.fail_on_advisory and counts["advisory"] > 0:
        return True
    return False


def build_report(
    *,
    input_path: str,
    plan_path: Optional[str],
    policy: Policy,
    metrics: VerifyMetrics,
    issues: Sequence[Issue],
) -> Dict[str, Any]:
    counts = _summarize_issues(issues)
    return {
        "c24_version": "C.24.8",
        "input": {"path": input_path, "bytes": os.path.getsize(input_path) if os.path.exists(input_path) else None},
        "plan": {"path": plan_path} if plan_path else None,
        "policy": {
            "fail_on_soft_warnings": policy.fail_on_soft_warnings,
            "fail_on_advisory": policy.fail_on_advisory,
            "max_redirect_chain": policy.max_redirect_chain,
            "allow_ambiguous_redirects": policy.allow_ambiguous_redirects,
            "allow_override_cross_jurisdiction": policy.allow_override_cross_jurisdiction,
            "allow_override_root_conflict": policy.allow_override_root_conflict,
            "min_events_for_auto_merge": policy.min_events_for_auto_merge,
            "check_events_against_redirects": policy.check_events_against_redirects,
        },
        "metrics": metrics.to_json(),
        "issue_counts": counts,
        "issues": [x.to_json() for x in issues],
        "pass": not _should_fail(issues, policy),
    }


# =============================================================================
# CLI
# =============================================================================

def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="C.24.8 – Place merge/split verifier (policy-driven severity)")
    p.add_argument("-i", "--input", required=True, help="Input JSON (C.24.7 export or later)")
    p.add_argument("--plan", default=None, help="Optional merge/split plan JSON")
    p.add_argument("--report", default=None, help="Write JSON report to path")
    p.add_argument("--debug", action="store_true", help="Enable debug logging")

    # CLI policy overrides (optional; plan.policy overrides are applied first, then CLI can override again)
    p.add_argument("--fail-on-soft", action="store_true", help="Fail if SOFT warnings exist")
    p.add_argument("--fail-on-advisory", action="store_true", help="Fail if ADVISORY warnings exist")
    p.add_argument("--max-chain", type=int, default=None, help="Max redirect chain depth")
    p.add_argument("--allow-ambiguous", action="store_true", help="Allow ambiguous redirect sets (NOT recommended)")
    p.add_argument("--no-event-check", action="store_true", help="Disable scanning events for ambiguity under redirects")
    return p


def main(argv: Optional[List[str]] = None) -> None:
    args = build_arg_parser().parse_args(argv)

    if args.debug:
        log.setLevel("DEBUG")

    log.info("Loading canonical export: %s", args.input)
    with open(args.input, "r", encoding="utf-8") as f:
        root = json.load(f)

    plan_obj: Optional[Dict[str, Any]] = None
    policy = Policy()

    if args.plan:
        log.info("Loading plan: %s", args.plan)
        plan_obj = _load_plan(args.plan)
        policy = Policy.from_plan(plan_obj)

    # CLI overrides (applied after plan policy)
    if args.fail_on_soft:
        policy.fail_on_soft_warnings = True
    if args.fail_on_advisory:
        policy.fail_on_advisory = True
    if isinstance(args.max_chain, int):
        policy.max_redirect_chain = int(args.max_chain)
    if args.allow_ambiguous:
        policy.allow_ambiguous_redirects = True
    if args.no_event_check:
        policy.check_events_against_redirects = False

    metrics, issues = verify_merge_split(root, policy=policy, plan=plan_obj)

    report = build_report(
        input_path=args.input,
        plan_path=args.plan,
        policy=policy,
        metrics=metrics,
        issues=issues,
    )

    if args.report:
        os.makedirs(os.path.dirname(args.report) or ".", exist_ok=True)
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

    fail = _should_fail(issues, policy)
    counts = report["issue_counts"]

    if fail:
        log.error(
            "Merge/split verification FAILED: hard=%d soft=%d advisory=%d",
            counts["hard"],
            counts["soft"],
            counts["advisory"],
        )
        # print a short human-readable summary (first 25)
        shown = 0
        for it in issues:
            if it.severity == Severity.HARD or policy.fail_on_soft_warnings or policy.fail_on_advisory:
                print(f"[{it.severity.value.upper()}] {it.rule_id} {it.pointer}: {it.message}")
                shown += 1
                if shown >= 25:
                    break
        raise SystemExit(1)

    log.info(
        "Merge/split verification PASSED: hard=%d soft=%d advisory=%d",
        counts["hard"],
        counts["soft"],
        counts["advisory"],
    )
    if args.report:
        print(f"[OK] Merge/split verification report written to: {args.report}")
    else:
        print("[OK] Merge/split verification passed")


if __name__ == "__main__":
    main()
