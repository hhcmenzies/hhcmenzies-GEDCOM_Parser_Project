#!/usr/bin/env python3
"""Preflight sanity checks for MA Notables collections config.

Supports:
  --user-agent
  --check-wikipedia
  --sleep
  --max-titles

Wikipedia will return HTTP 403 if you do not send a descriptive User-Agent.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests


def info(msg: str) -> None:
    print(msg)


def warn(msg: str) -> None:
    print(f"WARNING: {msg}", file=sys.stderr)


def die(msg: str, code: int = 2) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(code)


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def norm_title(t: str) -> str:
    return " ".join((t or "").strip().split())


@dataclass
class ResolveResult:
    ok: bool
    http_status: int
    normalized_title: Optional[str] = None


class WikiClient:
    def __init__(self, user_agent: str, sleep_s: float = 0.0) -> None:
        self.ua = user_agent
        self.sleep_s = max(0.0, sleep_s)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.ua})

    def _get(self, params: Dict[str, Any]) -> requests.Response:
        if self.sleep_s:
            time.sleep(self.sleep_s)
        return self.session.get("https://en.wikipedia.org/w/api.php", params=params, timeout=30)

    def resolve_title(self, title: str) -> ResolveResult:
        title = norm_title(title)
        r = self._get({"action": "query", "format": "json", "titles": title, "redirects": 1, "formatversion": 2})
        if r.status_code != 200:
            return ResolveResult(False, r.status_code, None)
        try:
            data = r.json()
        except Exception:
            return ResolveResult(False, r.status_code, None)
        pages = data.get("query", {}).get("pages", [])
        if not pages:
            return ResolveResult(False, r.status_code, None)
        page = pages[0]
        if page.get("missing"):
            return ResolveResult(False, r.status_code, None)
        return ResolveResult(True, r.status_code, page.get("title"))

    def category_member_probe(self, category_title: str, probe_limit: int = 1) -> int:
        ct = category_title
        if not ct.startswith("Category:"):
            ct = "Category:" + ct
        r = self._get({
            "action": "query", "format": "json",
            "list": "categorymembers",
            "cmtitle": ct,
            "cmlimit": str(max(1, min(500, probe_limit))),
            "cmtype": "page",
            "formatversion": 2,
        })
        r.raise_for_status()
        data = r.json()
        cms = data.get("query", {}).get("categorymembers", [])
        return len(cms)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="collections.json")
    ap.add_argument("--show", action="store_true", help="Print summary; no network needed")
    ap.add_argument("--user-agent", dest="user_agent", default="")
    ap.add_argument("--check-wikipedia", action="store_true")
    ap.add_argument("--sleep", type=float, default=0.0)
    ap.add_argument("--max-titles", type=int, default=500)
    args = ap.parse_args()

    cfg = load_json(args.config)
    proj = cfg.get("project", {})
    tw = proj.get("target_window", {})
    p_start = int(tw.get("start_year", 0) or 0)
    p_end = int(tw.get("end_year", 9999) or 9999)

    cols = cfg.get("collections", [])
    if not isinstance(cols, list) or not cols:
        die("No collections found in config.")

    slugs = [c.get("slug") for c in cols]
    if any(not s for s in slugs):
        die("One or more collections are missing a slug.")
    dup = sorted({s for s in slugs if slugs.count(s) > 1})
    if dup:
        die(f"Duplicate slugs found: {dup}")

    info(f"Config: {args.config}")
    info(f"Collections: {len(cols)}")
    info(f"Slugs: {slugs}")

    for c in cols:
        w = c.get("window", {}) or {}
        try:
            s = int(w.get("start_year"))
            e = int(w.get("end_year"))
        except Exception:
            die(f"{c.get('slug')}: window.start_year/end_year must be ints.")
        if s > e:
            die(f"{c.get('slug')}: window start_year > end_year ({s} > {e}).")
        if s < p_start or e > p_end:
            warn(f"{c.get('slug')}: window {s}-{e} exceeds project target_window {p_start}-{p_end} (pipeline may still filter).")

    for c in cols:
        if c.get("slug") != "shays_rebellion":
            continue
        sh_sources = c.get("sources", []) or []
        effective = [{
            "type": s.get("type"),
            "title": s.get("title") or "",
            "traverse_subcategories": bool(s.get("traverse_subcategories", False)),
        } for s in sh_sources if isinstance(s, dict)]
        info(f"EFFECTIVE SHAYS SOURCES: {effective}")
        for s in sh_sources:
            if s.get("type") == "list_page":
                if norm_title(s.get("title","")) != "Shays's Rebellion":
                    die("shays_rebellion list_page title must be exactly: Shays's Rebellion")
        break

    if args.show and not args.check_wikipedia:
        info("Preflight: OK (no network checks requested)")
        return 0

    if args.check_wikipedia:
        if not args.user_agent.strip():
            die("--user-agent is required when using --check-wikipedia")
        wc = WikiClient(user_agent=args.user_agent.strip(), sleep_s=args.sleep)

        checked = 0
        missing_titles: List[Tuple[str, str, str, int]] = []

        for c in cols:
            slug = c["slug"]
            for s in c.get("sources", []) or []:
                st = s.get("type") or "unknown"
                title = s.get("title") or ""
                if not title:
                    continue
                if checked >= args.max_titles:
                    break
                t = norm_title(title)
                res = wc.resolve_title(t)
                checked += 1
                if not res.ok:
                    missing_titles.append((slug, st, t, res.http_status))
                    warn(f"{slug}: {st} '{t}' -> NOT OK (HTTP {res.http_status})")
                    continue
                info(f"{slug}: {st} '{t}' -> OK")
                if st == "category":
                    try:
                        probe = wc.category_member_probe(res.normalized_title or t, probe_limit=1)
                        if probe == 0:
                            warn(f"{slug}: category '{res.normalized_title or t}' exists but has 0 page members (may yield 0 records).")
                    except Exception as e:
                        warn(f"{slug}: failed category probe for '{t}': {e}")

        info(f"Checked Wikipedia titles: {checked}")
        if missing_titles:
            warn(f"Missing/unresolvable titles: {len(missing_titles)} (showing up to 50)")
            for slug, st, t, http in missing_titles[:50]:
                warn(f"  {slug}: {st} -> {t} (HTTP {http})")

    info("Preflight: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
