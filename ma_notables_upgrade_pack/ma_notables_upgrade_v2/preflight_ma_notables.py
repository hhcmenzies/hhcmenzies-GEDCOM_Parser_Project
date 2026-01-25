#!/usr/bin/env python3
"""
Preflight sanity checks for MA Notables collections config.

Usage:
  python preflight_ma_notables.py --config collections.json \
    --user-agent "MA-Notables/1.0 (contact: you@example.com)" \
    --check-wikipedia \
    --max-titles 300

Notes:
- --check-wikipedia makes live calls to Wikipedia API (requires network).
- Wikipedia API requires a descriptive User-Agent; missing UA can cause HTTP 403.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests


# ----------------------------- helpers ----------------------------- #

def die(msg: str, code: int = 2) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)

def warn(msg: str) -> None:
    print(f"WARNING: {msg}", file=sys.stderr)

def info(msg: str) -> None:
    print(msg)

def is_int(x: Any) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)

def norm_title(t: str) -> str:
    # normalize whitespace only; MediaWiki title normalization is server-side
    return " ".join(t.strip().split())


@dataclass
class TitleCheck:
    ok: bool
    normalized_title: Optional[str]
    missing: bool
    ns: Optional[int]
    pageid: Optional[int]
    http_status: int
    content_type: str


class WikiClient:
    def __init__(self, user_agent: str, timeout: int = 30, sleep_s: float = 0.1):
        self.ua = user_agent
        self.timeout = timeout
        self.sleep_s = sleep_s
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": self.ua})

    def resolve_title(self, title: str) -> TitleCheck:
        title = norm_title(title)
        r = self.s.get(
            "https://en.wikipedia.org/w/api.php",
            params={"action": "query", "format": "json", "titles": title},
            timeout=self.timeout,
        )
        ct = (r.headers.get("Content-Type") or "").lower()
        if r.status_code != 200:
            return TitleCheck(
                ok=False,
                normalized_title=None,
                missing=True,
                ns=None,
                pageid=None,
                http_status=r.status_code,
                content_type=ct,
            )
        if "json" not in ct:
            return TitleCheck(
                ok=False,
                normalized_title=None,
                missing=True,
                ns=None,
                pageid=None,
                http_status=r.status_code,
                content_type=ct,
            )
        data = r.json()
        pages = data.get("query", {}).get("pages", {})
        page = next(iter(pages.values())) if pages else {}
        missing = bool(page.get("missing"))
        # Respect politeness
        if self.sleep_s:
            time.sleep(self.sleep_s)
        return TitleCheck(
            ok=not missing,
            normalized_title=page.get("title"),
            missing=missing,
            ns=page.get("ns"),
            pageid=page.get("pageid"),
            http_status=r.status_code,
            content_type=ct,
        )

    def category_member_count(self, category_title: str, limit_probe: int = 1) -> int:
        """
        Returns number of category members (pages only) if we page through everything.
        For preflight, we usually only need to know if it is zero/non-zero.
        If limit_probe==1: returns 0 or >=1 depending on whether any members exist.
        """
        category_title = norm_title(category_title)
        cmcontinue = None
        count = 0
        while True:
            params = {
                "action": "query",
                "format": "json",
                "list": "categorymembers",
                "cmtitle": category_title,
                "cmlimit": "500",
                "cmtype": "page",
            }
            if cmcontinue:
                params["cmcontinue"] = cmcontinue
            r = self.s.get("https://en.wikipedia.org/w/api.php", params=params, timeout=self.timeout)
            r.raise_for_status()
            data = r.json()
            members = data.get("query", {}).get("categorymembers", []) or []
            count += len(members)
            if limit_probe == 1 and count >= 1:
                if self.sleep_s:
                    time.sleep(self.sleep_s)
                return count
            if "continue" not in data:
                break
            cmcontinue = data["continue"]["cmcontinue"]
            if self.sleep_s:
                time.sleep(self.sleep_s)
        return count


# ----------------------------- validation ----------------------------- #

def validate_config_structure(cfg: Dict[str, Any]) -> List[str]:
    errors: List[str] = []

    if not isinstance(cfg, dict):
        return ["Config root must be a JSON object"]

    proj = cfg.get("project")
    if not isinstance(proj, dict):
        errors.append("Missing or invalid 'project' object")
    else:
        tw = proj.get("target_window")
        if not isinstance(tw, dict):
            errors.append("Missing or invalid project.target_window object")
        else:
            sy, ey = tw.get("start_year"), tw.get("end_year")
            if not (is_int(sy) and is_int(ey)):
                errors.append("project.target_window.start_year and end_year must be integers")
            elif sy > ey:
                errors.append("project.target_window.start_year must be <= end_year")

    cols = cfg.get("collections")
    if not isinstance(cols, list) or not cols:
        errors.append("Missing or invalid 'collections' array (must be non-empty)")
        return errors

    for i, c in enumerate(cols):
        path = f"collections[{i}]"
        if not isinstance(c, dict):
            errors.append(f"{path} must be an object")
            continue

        for req in ("slug", "label", "association", "window", "sources"):
            if req not in c:
                errors.append(f"{path} missing required key '{req}'")

        slug = c.get("slug")
        if not isinstance(slug, str) or not slug.strip():
            errors.append(f"{path}.slug must be a non-empty string")

        label = c.get("label")
        if not isinstance(label, str) or not label.strip():
            errors.append(f"{path}.label must be a non-empty string")

        assoc = c.get("association")
        if not isinstance(assoc, dict):
            errors.append(f"{path}.association must be an object")
        else:
            at = assoc.get("type")
            al = assoc.get("label")
            if at not in ("categorized_as", "event_in", "period_in"):
                errors.append(f"{path}.association.type must be one of categorized_as|event_in|period_in")
            if not isinstance(al, str) or not al.strip():
                errors.append(f"{path}.association.label must be a non-empty string")

        win = c.get("window")
        if not isinstance(win, dict):
            errors.append(f"{path}.window must be an object")
        else:
            sy, ey = win.get("start_year"), win.get("end_year")
            if not (is_int(sy) and is_int(ey)):
                errors.append(f"{path}.window.start_year and end_year must be integers")
            elif sy > ey:
                errors.append(f"{path}.window.start_year must be <= end_year")

        sources = c.get("sources")
        if not isinstance(sources, list) or not sources:
            errors.append(f"{path}.sources must be a non-empty array")
        else:
            for j, s in enumerate(sources):
                sp = f"{path}.sources[{j}]"
                if not isinstance(s, dict):
                    errors.append(f"{sp} must be an object")
                    continue
                st = s.get("type")
                title = s.get("title")
                if st not in ("category", "list_page"):
                    errors.append(f"{sp}.type must be 'category' or 'list_page'")
                if not isinstance(title, str) or not title.strip():
                    errors.append(f"{sp}.title must be a non-empty string")
                tsc = s.get("traverse_subcategories", False)
                if st == "list_page" and tsc not in (False, None):
                    # keep as a warning not an error; we tolerate it
                    pass

    return errors


def validate_semantics(cfg: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """Returns (errors, warnings)."""
    errors: List[str] = []
    warnings: List[str] = []

    tw = cfg["project"]["target_window"]
    p_sy, p_ey = tw["start_year"], tw["end_year"]

    slugs = []
    for c in cfg["collections"]:
        slugs.append(c["slug"])

        # window within project window (warn, not error, because sometimes you intentionally overlap)
        w = c["window"]
        sy, ey = w["start_year"], w["end_year"]
        if sy < p_sy or ey > p_ey:
            warnings.append(
                f"Collection '{c['slug']}' window {sy}-{ey} exceeds project target {p_sy}-{p_ey}"
            )

    # unique slugs
    seen = set()
    dups = set()
    for s in slugs:
        if s in seen:
            dups.add(s)
        seen.add(s)
    if dups:
        errors.append(f"Duplicate slugs found: {sorted(dups)}")

    return errors, warnings


# ----------------------------- main ----------------------------- #

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, help="Path to collections.json")
    ap.add_argument("--user-agent", default="", help="User-Agent string for Wikipedia API checks")
    ap.add_argument("--check-wikipedia", action="store_true", help="Resolve titles against Wikipedia API")
    ap.add_argument("--max-titles", type=int, default=400, help="Max titles to check against Wikipedia")
    ap.add_argument("--sleep", type=float, default=0.1, help="Sleep between Wikipedia requests (seconds)")
    args = ap.parse_args()

    try:
        cfg = json.load(open(args.config, "r", encoding="utf-8"))
    except Exception as e:
        die(f"Failed to parse JSON config '{args.config}': {e}")

    info(f"Config: {args.config}")

    struct_errors = validate_config_structure(cfg)
    if struct_errors:
        for e in struct_errors:
            print(f"ERROR: {e}", file=sys.stderr)
        return 2

    sem_errors, sem_warnings = validate_semantics(cfg)
    for w in sem_warnings:
        warn(w)
    if sem_errors:
        for e in sem_errors:
            print(f"ERROR: {e}", file=sys.stderr)
        return 2

    cols = cfg["collections"]
    info(f"Collections: {len(cols)}")
    info(f"Slugs: {[c['slug'] for c in cols]}")

    # Print Shays effective sources if present
    for c in cols:
        if c.get("slug") == "shays_rebellion":
            info(f"EFFECTIVE SHAYS SOURCES: {c.get('sources', [])}")

    # Wikipedia checks
    if args.check_wikipedia:
        if not args.user_agent.strip():
            die("--check-wikipedia requires --user-agent (Wikipedia may 403 without it).")

        wc = WikiClient(user_agent=args.user_agent.strip(), sleep_s=max(0.0, args.sleep))
        checked = 0
        missing_titles: List[Tuple[str, str, str]] = []  # (slug, source_type, title)
        normalized_map: List[Tuple[str, str, str, str]] = []  # (slug, type, original, normalized)

        # gather titles
        for c in cols:
            slug = c["slug"]
            for s in c.get("sources", []):
                st = s.get("type")
                title = s.get("title")
                if not title:
                    continue
                if checked >= args.max_titles:
                    break

                t = norm_title(title)
                res = wc.resolve_title(t)
                checked += 1

                if not res.ok:
                    missing_titles.append((slug, st, t))
                    warn(f"{slug}: {st} '{t}' -> MISSING/NOT-OK (HTTP {res.http_status})")
                else:
                    if res.normalized_title and res.normalized_title != t:
                        normalized_map.append((slug, st, t, res.normalized_title))
                        info(f"{slug}: {st} '{t}' -> OK (normalized: '{res.normalized_title}')")
                    else:
                        info(f"{slug}: {st} '{t}' -> OK")

                # extra: categories often exist but are empty
                if st == "category" and res.ok:
                    try:
                        probe = wc.category_member_count(res.normalized_title or t, limit_probe=1)
                        if probe == 0:
                            warn(f"{slug}: category '{res.normalized_title or t}' exists but has 0 page members (may yield 0 records).")
                    except Exception as e:
                        warn(f"{slug}: failed to probe categorymembers for '{t}': {e}")

        info(f"Checked Wikipedia titles: {checked}")

        if missing_titles:
            warn(f"Missing/unresolvable titles: {len(missing_titles)}")
            for slug, st, t in missing_titles[:50]:
                warn(f"  {slug}: {st} -> {t}")
            # don't hard-fail; some categories are optional or exist under different names
        else:
            info("All checked titles resolved OK.")

        if normalized_map:
            info("Titles normalized by Wikipedia:")
            for slug, st, orig, normed in normalized_map[:50]:
                info(f"  {slug}: {st}: '{orig}' -> '{normed}'")

    info("Preflight: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
