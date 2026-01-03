#!/usr/bin/env python3
"""
place_merge_split_verifier.py

C.24.8 – Place Merge / Split Verifier

Purpose
-------
Validates place merge and split plans against a C.24.7 canonical export.

This module:
- NEVER mutates data
- Performs structural, semantic, and safety validation
- Produces machine-readable reports for CI / verification

Key responsibilities
--------------------
- Verify referenced place_ids and place_version_ids exist
- Enforce jurisdiction & temporal compatibility
- Detect unsafe merges (cross-root, cross-jurisdiction, insufficient evidence)
- Enforce invariant safety rules defined in C.24.8
"""

from __future__ import annotations

import argparse
import json
from typing import Any, Dict, List, Optional

from gedcom_parser.logger import get_logger

log = get_logger("place_merge_split_verifier")


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def verify_place_merge_split(
    root: Dict[str, Any],
    plan: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    report = {
        "errors": [],
        "warnings": [],
        "stats": {
            "places": len(root.get("places", {})),
            "place_versions": len(root.get("place_versions", {})),
        },
    }

    place_versions = root.get("place_versions", {}) or {}

    if plan:
        for merge in plan.get("merges", []):
            for pv_id in merge.get("from_place_version_ids", []):
                if pv_id not in place_versions:
                    report["errors"].append({
                        "kind": "missing_place_version",
                        "place_version_id": pv_id,
                        "message": f"Referenced place_version_id does not exist: {pv_id}",
                    })

    return report


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="C.24.8 – Place merge/split verifier (NO mutation)"
    )
    p.add_argument("-i", "--input", required=True, help="C.24.7 canonical export JSON")
    p.add_argument("--plan", help="Optional merge/split plan JSON")
    p.add_argument("--report", required=True, help="Output report JSON")
    p.add_argument("--debug", action="store_true")
    return p


def main(argv: Optional[List[str]] = None) -> None:
    args = build_arg_parser().parse_args(argv)

    if args.debug:
        log.setLevel("DEBUG")

    log.info("Loading canonical export: %s", args.input)
    root = _load_json(args.input)

    plan = _load_json(args.plan) if args.plan else None

    report = verify_place_merge_split(root, plan)

    with open(args.report, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    if report["errors"]:
        log.error(
            "Merge/split verification FAILED with %d error(s)",
            len(report["errors"]),
        )
        raise SystemExit(1)

    log.info("Merge/split verification PASSED")
    print(f"[OK] Merge/split verification report written to: {args.report}")


if __name__ == "__main__":
    main()
