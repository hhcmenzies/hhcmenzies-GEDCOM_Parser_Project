#!/usr/bin/env python3
"""
preflight_ma_notables.py

Sanity checks for MA Notables collections config.

What it does:
- Validates JSON structure + uniqueness of slugs
- Warns when collection windows exceed project target_window
- (optional) checks that every Wikipedia title resolves
- (optional) for Category: sources, probes whether the category has at least 1 page member
- Limits checks per-source with --max-titles, and throttles with --sleep

This script is intentionally standalone (requests only).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests


def norm_title(title: str) -> str:
    title = (title or "").strip()
    title = re.sub(r"\s+", " ", title)
    if not title:
        return title
    return title[0].upper() + title[1:]


@dataclass
class ResolveResult:
    ok: bool
    status_code: int
    normalized_title: Optional[str] = None
    missing: bool = False
    note: str = ""


class WikiClient:
    def __init__(self, user_agent: str, timeout: float = 30.0, sleep_s: float = 0.0):
        if not user_agent or "contact:" not in user_agent:
            # Not strictly required, but helps avoid 403s / blocks.
            raise ValueError("Please pass a descriptive --user-agent that includes contact info, e.g. "
                             "'MA-Notables/1.0 (contact: you@example.com)'")
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": user_agent})
        self.timeout = timeout
        self.sleep_s = max(0.0, float(sleep_s))

    def _get(self, params: Dict[str, Any]) -> requests.Response:
        r = self.s.get("https://en.wikipedia.org/w/api.php", params=params, timeout=self.timeout)
        r.raise_for_status()
        return r

    def resolve_title(self, title: str) -> ResolveResult:
        title = norm_title(title)
        params = {"action": "query", "format": "json", "titles": title}
        try:
            r = self._get(params)
            data = r.json()
            pages = data.get("query", {}).get("pages", {})
            page = next(iter(pages.values())) if pages else {}
            missing = bool(page.get("missing"))
            normalized = page.get("title") if isinstance(page, dict) else None
            return ResolveResult(ok=not missing, status_code=r.status_code, normalized_title=normalized, missing=missing)
        except Exception as e:
            return ResolveResult(ok=False, status_code=getattr(getattr(e, "response", None), "status_code", 0) or 0, note=str(e))

    def category_has_members(self, category_title: str) -> Tuple[bool, int]:
        """
        Returns (has_members, n_found_when_probing).
        We "probe" cheaply: stop as soon as we see 1 page member.
        """
        category_title = norm_title(category_title)
        cmcontinue = None
        seen = 0
        while True:
            params = {
                "action": "query",
                "format": "json",
                "list": "categorymembers",
                "cmtitle": category_title,
                "cmlimit": "50",
                "cmtype": "page",
            }
            if cmcontinue:
                params["cmcontinue"] = cmcontinue
            r = self._get(params)
            data = r.json()
            members = data.get("query", {}).get("categorymembers", []) or []
            seen += len(members)
            if seen >= 1:
                return True, seen
            cont = data.get("continue", {})
            if not cont:
                return False, seen
            cmcontinue = cont.get("cmcontinue")
            if self.sleep_s:
                time.sleep(self.sleep_s)


def load_config(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_config(cfg: Dict[str, Any]) -> List[str]:
    errs: List[str] = []
    if "project" not in cfg or "target_window" not in cfg["project"]:
        errs.append("Missing cfg.project.target_window")
    if "collections" not in cfg or not isinstance(cfg["collections"], list) or not cfg["collections"]:
        errs.append("Missing cfg.collections (non-empty list)")
    slugs = []
    for i, c in enumerate(cfg.get("collections", []), start=1):
        if not isinstance(c, dict):
            errs.append(f"collections[{i}] must be an object")
            continue
        slug = c.get("slug")
        if not slug or not isinstance(slug, str):
            errs.append(f"collections[{i}] missing slug")
        else:
            slugs.append(slug)
        if "sources" not in c or not isinstance(c["sources"], list) or not c["sources"]:
            errs.append(f"{slug or f'collections[{i}]'} missing sources")
    # unique slugs
    if len(set(slugs)) != len(slugs):
        dups = sorted({s for s in slugs if slugs.count(s) > 1})
        errs.append(f"Duplicate slugs: {dups}")
    return errs


def iter_titles(cfg: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
    """
    Returns list of (collection_slug, source) tuples.
    """
    out: List[Tuple[str, Dict[str, Any]]] = []
    for c in cfg.get("collections", []):
        slug = c.get("slug", "unknown")
        for s in c.get("sources", []):
            if not isinstance(s, dict):
                continue
            if "title" in s:
                out.append((slug, s))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="collections.json")
    ap.add_argument("--show", action="store_true", help="Print summary (collections + slugs)")
    ap.add_argument("--user-agent", default=None, help="User-Agent to use for Wikipedia checks")
    ap.add_argument("--check-wikipedia", action="store_true", help="Resolve titles via Wikipedia API")
    ap.add_argument("--sleep", type=float, default=0.1, help="Delay between Wikipedia requests")
    ap.add_argument("--max-titles", type=int, default=500, help="Cap number of Wikipedia titles checked")
    args = ap.parse_args()

    cfg = load_config(args.config)

    errs = validate_config(cfg)
    if errs:
        print("Config errors:", file=sys.stderr)
        for e in errs:
            print("  -", e, file=sys.stderr)
        return 2

    project = cfg["project"]["target_window"]
    p_start = int(project.get("start_year", 0) or 0)
    p_end = int(project.get("end_year", 0) or 0)

    slugs = [c["slug"] for c in cfg["collections"]]
    print(f"Config: {args.config}")
    print(f"Collections: {len(slugs)}")
    print("Slugs:", slugs)

    # window warnings
    for c in cfg["collections"]:
        w = c.get("window") or {}
        c_start = int(w.get("start_year", p_start) or p_start)
        c_end = int(w.get("end_year", p_end) or p_end)
        if c_start < p_start or c_end > p_end:
            print(f"WARNING: {c.get('slug')}: window {c_start}-{c_end} exceeds project target_window {p_start}-{p_end} (pipeline may still filter).")

    if args.show and not args.check_wikipedia:
        return 0

    if args.check_wikipedia:
        if not args.user_agent:
            print("ERROR: --check-wikipedia requires --user-agent", file=sys.stderr)
            return 2
        wc = WikiClient(user_agent=args.user_agent, sleep_s=args.sleep)

        missing: List[str] = []
        checked = 0

        for slug, src in iter_titles(cfg)[: max(0, args.max_titles)]:
            stype = src.get("type")
            title = norm_title(src.get("title", ""))
            if not title:
                continue

            res = wc.resolve_title(title)
            ok = res.ok
            # For categories, also probe for at least one member (common source of "exists but empty")
            if ok and stype == "category":
                has_members, seen = wc.category_has_members(title)
                if not has_members:
                    ok = False
                    res.note = f"category has 0 page members (probe={seen})"

            status = "OK" if ok else "NOT OK"
            extra = f" | {res.note}" if res.note else ""
            print(f"{slug}: {stype} '{title}' -> {status} (HTTP {res.status_code}){extra}")

            checked += 1
            if not ok:
                missing.append(f"{slug}: {stype} -> {title} (HTTP {res.status_code}){extra}")

            if args.sleep:
                time.sleep(args.sleep)

        print(f"Checked Wikipedia titles: {checked}")
        if missing:
            print(f"WARNING: Missing/unresolvable titles: {len(missing)} (showing up to 50)")
            for m in missing[:50]:
                print("WARNING:  ", m)

    print("Preflight: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
