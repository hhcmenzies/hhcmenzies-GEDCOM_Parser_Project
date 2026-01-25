#!/usr/bin/env python3
"""
ma_notables_pipeline.py (upgrade pack v3)

Goal
----
Build a master dataset of notable *people* connected to Massachusetts via
event/period/list/category associations (1600–1799 by default), normalize key
biographic fields via Wikidata, and produce derived "collection" datasets.

Key upgrades vs earlier versions
--------------------------------
1) Config v2 support (project.target_window + collections[].sources[])
2) Human-only gate: Wikidata P31 must include Q5 (human)
3) Date precision stored separately (no multi-value date fields)
4) Quarantine outputs (so you can audit exclusions)
5) QA report with missingness + coverage metrics
6) Basic config sanity checks + optional schema_version

No brittle HTML scraping: uses MediaWiki action API + Wikidata wbgetentities.

Dependencies: requests
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import requests

WIKI_API = "https://en.wikipedia.org/w/api.php"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"

DEFAULT_USER_AGENT = "MA-Notables-Pipeline/3.0 (contact: you@example.com)"
DEFAULT_OUTDIR = "out"
DEFAULT_MASTER_FILE = "master_ma_1600_1799.jsonl"

# Prevent runaway category explosions
MAX_PAGES_PER_COLLECTION = 50000


# ---------------------------
# API client
# ---------------------------

class ApiClient:
    def __init__(self, user_agent: str, sleep_s: float = 0.15, timeout_s: int = 30):
        self.sess = requests.Session()
        self.sess.headers.update({"User-Agent": user_agent})
        self.sleep_s = sleep_s
        self.timeout_s = timeout_s

    def get_json(self, url: str, params: dict, retries: int = 7) -> dict:
        for attempt in range(retries):
            r = self.sess.get(url, params=params, timeout=self.timeout_s)
            if r.status_code == 429:
                # exponential backoff
                time.sleep(min(10.0, 2 ** attempt))
                continue
            r.raise_for_status()
            return r.json()
        raise RuntimeError(f"Failed after retries: {url} params={params}")

    def polite_sleep(self):
        time.sleep(self.sleep_s)


# ---------------------------
# Config model (v2)
# ---------------------------

@dataclass(frozen=True)
class SourceDef:
    type: str  # "category" or "list_page"
    title: str
    traverse_subcategories: bool = False

@dataclass(frozen=True)
class CollectionDef:
    slug: str
    label: str
    description: Optional[str]
    association_type: str
    association_label: str
    window_start_year: Optional[int]
    window_end_year: Optional[int]
    sources: List[SourceDef]

@dataclass(frozen=True)
class ProjectConfig:
    schema_version: str
    target_start_year: int
    target_end_year: int
    collections: List[CollectionDef]


def _fail(msg: str) -> None:
    print(f"[config error] {msg}", file=sys.stderr)
    raise SystemExit(2)


def load_config(path: str) -> ProjectConfig:
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    schema_version = str(obj.get("schema_version", "2.0"))

    project = obj.get("project")
    if not isinstance(project, dict):
        _fail("Missing or invalid 'project' object")
    tw = project.get("target_window")
    if not isinstance(tw, dict):
        _fail("Missing or invalid 'project.target_window' object")

    try:
        target_start = int(tw["start_year"])
        target_end = int(tw["end_year"])
    except Exception:
        _fail("project.target_window must include integer start_year and end_year")

    if target_start > target_end:
        _fail("project.target_window.start_year must be <= end_year")

    collections_raw = obj.get("collections")
    if not isinstance(collections_raw, list) or not collections_raw:
        _fail("Missing or invalid 'collections' list")

    collections: List[CollectionDef] = []
    seen_slugs: Set[str] = set()

    for c in collections_raw:
        if not isinstance(c, dict):
            _fail("Each item in collections must be an object")

        slug = c.get("slug")
        label = c.get("label")
        if not isinstance(slug, str) or not re.match(r"^[a-z0-9_\-]+$", slug):
            _fail(f"Invalid slug: {slug!r} (must match ^[a-z0-9_\\-]+$)")
        if slug in seen_slugs:
            _fail(f"Duplicate collection slug: {slug}")
        seen_slugs.add(slug)

        if not isinstance(label, str) or not label.strip():
            _fail(f"Collection {slug}: missing/invalid label")

        assoc = c.get("association")
        if not isinstance(assoc, dict):
            _fail(f"Collection {slug}: missing/invalid association")
        assoc_type = assoc.get("type", "event_in")
        assoc_label = assoc.get("label", label)
        if not isinstance(assoc_type, str) or not assoc_type:
            _fail(f"Collection {slug}: association.type must be a non-empty string")
        if not isinstance(assoc_label, str) or not assoc_label:
            _fail(f"Collection {slug}: association.label must be a non-empty string")

        win = c.get("window", {})
        if not isinstance(win, dict):
            _fail(f"Collection {slug}: window must be an object")
        ws = win.get("start_year")
        we = win.get("end_year")
        if ws is not None and not isinstance(ws, int):
            _fail(f"Collection {slug}: window.start_year must be int or null")
        if we is not None and not isinstance(we, int):
            _fail(f"Collection {slug}: window.end_year must be int or null")

        sources_raw = c.get("sources")
        if not isinstance(sources_raw, list) or not sources_raw:
            _fail(f"Collection {slug}: sources must be a non-empty list")

        sources: List[SourceDef] = []
        for s in sources_raw:
            if not isinstance(s, dict):
                _fail(f"Collection {slug}: each source must be an object")
            stype = s.get("type")
            title = s.get("title")
            if stype not in ("category", "list_page"):
                _fail(f"Collection {slug}: source.type must be 'category' or 'list_page'")
            if not isinstance(title, str) or not title.strip():
                _fail(f"Collection {slug}: source.title must be a non-empty string")
            traverse = bool(s.get("traverse_subcategories", False))
            sources.append(SourceDef(type=stype, title=title, traverse_subcategories=traverse))

        collections.append(CollectionDef(
            slug=slug,
            label=label.strip(),
            description=c.get("description"),
            association_type=assoc_type,
            association_label=assoc_label,
            window_start_year=ws,
            window_end_year=we,
            sources=sources,
        ))

    return ProjectConfig(
        schema_version=schema_version,
        target_start_year=target_start,
        target_end_year=target_end,
        collections=collections,
    )


# ---------------------------
# Wikipedia harvesting
# ---------------------------

def wikipedia_category_members(api: ApiClient, category_title: str, cmtype: str = "page|subcat") -> Tuple[Set[str], Set[str]]:
    pages: Set[str] = set()
    subcats: Set[str] = set()
    cmcontinue = None

    while True:
        params = {
            "action": "query",
            "format": "json",
            "list": "categorymembers",
            "cmtitle": category_title,
            "cmtype": cmtype,
            "cmlimit": "max",
        }
        if cmcontinue:
            params["cmcontinue"] = cmcontinue

        data = api.get_json(WIKI_API, params)
        members = data.get("query", {}).get("categorymembers", [])
        for m in members:
            title = m.get("title")
            ns = m.get("ns")
            if not title:
                continue
            if ns == 0:
                pages.add(title)
            elif ns == 14:
                subcats.add(title)

        cmcontinue = data.get("continue", {}).get("cmcontinue")
        if not cmcontinue:
            break

        api.polite_sleep()

    return pages, subcats


def harvest_from_category(api: ApiClient, cat_title: str, traverse: bool) -> Set[str]:
    seen: Set[str] = set()
    queue: List[str] = [cat_title]
    titles: Set[str] = set()

    while queue:
        cat = queue.pop(0)
        if cat in seen:
            continue
        seen.add(cat)

        pages, subcats = wikipedia_category_members(api, cat, cmtype="page|subcat")
        titles |= pages

        if traverse:
            for sc in sorted(subcats):
                if sc not in seen:
                    queue.append(sc)

        if len(titles) > MAX_PAGES_PER_COLLECTION:
            raise RuntimeError(
                f"Exceeded MAX_PAGES_PER_COLLECTION={MAX_PAGES_PER_COLLECTION} "
                f"while harvesting {cat_title}. Narrow sources or raise the cap."
            )

        api.polite_sleep()

    return titles


def harvest_from_list_page(api: ApiClient, page_title: str) -> Set[str]:
    """
    Harvest main-namespace links from a list page (prop=links with continuation).
    """
    titles: Set[str] = set()
    plcontinue = None

    while True:
        params = {
            "action": "query",
            "format": "json",
            "titles": page_title,
            "prop": "links",
            "plnamespace": 0,
            "pllimit": "max",
        }
        if plcontinue:
            params["plcontinue"] = plcontinue

        data = api.get_json(WIKI_API, params)
        pages = data.get("query", {}).get("pages", {})
        for _, p in pages.items():
            for link in p.get("links", []):
                t = link.get("title")
                if t:
                    titles.add(t)

        plcontinue = data.get("continue", {}).get("plcontinue")
        if not plcontinue:
            break

        api.polite_sleep()

    return titles


def fetch_wikipedia_pageprops_extracts(api: ApiClient, titles: List[str]) -> Dict[str, dict]:
    """
    Returns mapping: title -> {pageid, wikibase_item, extract}
    """
    out: Dict[str, dict] = {}
    for batch in chunked(titles, 50):
        params = {
            "action": "query",
            "format": "json",
            "redirects": 1,
            "prop": "pageprops|extracts",
            "exintro": 1,
            "explaintext": 1,
            "titles": "|".join(batch),
        }
        data = api.get_json(WIKI_API, params)
        pages = data.get("query", {}).get("pages", {})
        for _, p in pages.items():
            if p.get("missing"):
                continue
            title = p.get("title")
            if not title:
                continue
            out[title] = {
                "pageid": p.get("pageid"),
                "wikibase_item": p.get("pageprops", {}).get("wikibase_item"),
                "extract": (p.get("extract") or "").strip(),
            }
        api.polite_sleep()
    return out


def chunked(items: List[str], n: int) -> Iterable[List[str]]:
    for i in range(0, len(items), n):
        yield items[i:i + n]


# ---------------------------
# Wikidata helpers
# ---------------------------

def wikidata_wbgetentities(api: ApiClient, ids: List[str], props: str) -> dict:
    params = {"action": "wbgetentities", "format": "json", "ids": "|".join(ids), "props": props}
    return api.get_json(WIKIDATA_API, params)


def _first_claim(entity: dict, pid: str) -> Optional[dict]:
    claims = entity.get("claims", {}).get(pid, [])
    return claims[0] if claims else None


def get_time_claim(entity: dict, pid: str) -> Tuple[Optional[str], Optional[int]]:
    """
    Returns (time_str, precision_int)
    """
    c = _first_claim(entity, pid)
    if not c:
        return None, None
    val = c.get("mainsnak", {}).get("datavalue", {}).get("value", {})
    return val.get("time"), val.get("precision")


def get_entity_claim(entity: dict, pid: str) -> Optional[str]:
    c = _first_claim(entity, pid)
    if not c:
        return None
    val = c.get("mainsnak", {}).get("datavalue", {}).get("value", {})
    return val.get("id")


def get_entity_claims(entity: dict, pid: str, limit: int = 7) -> List[str]:
    out = []
    claims = entity.get("claims", {}).get(pid, [])
    for c in claims[:limit]:
        val = c.get("mainsnak", {}).get("datavalue", {}).get("value", {})
        qid = val.get("id")
        if qid:
            out.append(qid)
    return out


def is_human(entity: dict) -> bool:
    """
    Human = instance of (P31) includes Q5.
    """
    for qid in get_entity_claims(entity, "P31", limit=20):
        if qid == "Q5":
            return True
    return False


def iso_year(timestr: Optional[str]) -> Optional[int]:
    if not timestr:
        return None
    m = re.match(r"^[+-]?(\d+)-", timestr)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def iso_date(timestr: Optional[str]) -> Optional[str]:
    if not timestr:
        return None
    m = re.match(r"^[+-]?(\d+)-(\d{2})-(\d{2})T", timestr)
    if m:
        y, mo, d = m.group(1), m.group(2), m.group(3)
        return f"{int(y):04d}-{mo}-{d}"
    y = iso_year(timestr)
    return f"{y:04d}" if y is not None else None


def precision_label(p: Optional[int]) -> Optional[str]:
    """
    Wikidata time precision:
      11 = day, 10 = month, 9 = year, 8 = decade, 7 = century, 6 = millennium
    """
    if p is None:
        return None
    return {
        11: "day",
        10: "month",
        9: "year",
        8: "decade",
        7: "century",
        6: "millennium",
    }.get(p, f"precision_{p}")


def fetch_labels(api: ApiClient, qids: Set[str]) -> Dict[str, str]:
    labels: Dict[str, str] = {}
    if not qids:
        return labels
    for batch in chunked(sorted(qids), 50):
        data = wikidata_wbgetentities(api, batch, props="labels")
        ents = data.get("entities", {})
        for qid, e in ents.items():
            lab = e.get("labels", {}).get("en", {}).get("value")
            if lab:
                labels[qid] = lab
        api.polite_sleep()
    return labels


# ---------------------------
# Inclusion logic
# ---------------------------

def overlaps(target_start: int, target_end: int, a_start: Optional[int], a_end: Optional[int]) -> bool:
    """
    Association window overlaps target window.
    If both bounds missing, treat as overlapping (still valid event-based link).
    """
    if a_start is None and a_end is None:
        return True
    s = a_start if a_start is not None else target_start
    e = a_end if a_end is not None else target_end
    return not (e < target_start or s > target_end)


# ---------------------------
# Output helpers
# ---------------------------

def ensure_dir(p: str) -> None:
    os.makedirs(p, exist_ok=True)

def write_jsonl(path: str, records: Iterable[dict]) -> int:
    n = 0
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            n += 1
    return n

def write_json(path: str, obj: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


# ---------------------------
# Build datasets
# ---------------------------

def build(api: ApiClient, cfg: ProjectConfig, outdir: str) -> None:
    # Harvest titles per collection
    collection_titles: Dict[str, Set[str]] = {}

    for c in cfg.collections:
        titles: Set[str] = set()
        for src in c.sources:
            if src.type == "category":
                titles |= harvest_from_category(api, src.title, src.traverse_subcategories)
            elif src.type == "list_page":
                titles |= harvest_from_list_page(api, src.title)
            else:
                raise ValueError(f"Unknown source type: {src.type}")
        collection_titles[c.slug] = titles

    # Union all titles
    all_titles: Set[str] = set()
    for tset in collection_titles.values():
        all_titles |= tset
    all_titles_list = sorted(all_titles)

    # Fetch Wikipedia pageprops + extracts
    wp_meta = fetch_wikipedia_pageprops_extracts(api, all_titles_list)

    # Prepare membership lookup: title -> collections
    title_membership: Dict[str, List[CollectionDef]] = {}
    for c in cfg.collections:
        for title in collection_titles.get(c.slug, set()):
            title_membership.setdefault(title, []).append(c)

    # Collect QIDs
    title_to_qid: Dict[str, str] = {}
    for title, m in wp_meta.items():
        qid = m.get("wikibase_item")
        if qid:
            title_to_qid[title] = qid

    qids = sorted(set(title_to_qid.values()))

    # Fetch Wikidata entities (claims + labels + descriptions for fallback notability)
    entities: Dict[str, dict] = {}
    for batch in chunked(qids, 50):
        data = wikidata_wbgetentities(api, batch, props="claims|labels|descriptions")
        entities.update(data.get("entities", {}))
        api.polite_sleep()

    # Gather place + occupation qids for labels
    place_qids: Set[str] = set()
    occ_qids: Set[str] = set()
    for qid, ent in entities.items():
        pob = get_entity_claim(ent, "P19")
        pod = get_entity_claim(ent, "P20")
        if pob:
            place_qids.add(pob)
        if pod:
            place_qids.add(pod)
        for oq in get_entity_claims(ent, "P106", limit=10):
            occ_qids.add(oq)

    place_labels = fetch_labels(api, place_qids)
    occ_labels = fetch_labels(api, occ_qids)

    # Output dirs
    ensure_dir(outdir)
    collections_dir = os.path.join(outdir, "collections")
    ensure_dir(collections_dir)

    # Quarantine files
    rejected_no_qid_path = os.path.join(outdir, "rejected_no_qid.jsonl")
    rejected_nonhuman_path = os.path.join(outdir, "rejected_nonhuman.jsonl")
    rejected_outside_path = os.path.join(outdir, "rejected_outside_window.jsonl")

    # Master + per-collection accumulators
    master_by_id: Dict[str, dict] = {}
    per_collection: Dict[str, List[dict]] = {c.slug: [] for c in cfg.collections}

    # QA counters
    qa = {
        "schema_version": "1.1",
        "target_window": {"start_year": cfg.target_start_year, "end_year": cfg.target_end_year},
        "counts": {
            "candidates_total_titles": len(all_titles_list),
            "candidates_with_wp_meta": len(wp_meta),
            "candidates_with_qid": 0,
            "rejected_no_qid": 0,
            "rejected_nonhuman": 0,
            "rejected_outside_window": 0,
            "included_master_records": 0,
        },
        "missingness_in_master": {
            "birth_date_missing": 0,
            "birth_place_missing": 0,
            "death_date_missing": 0,
            "death_place_missing": 0,
            "notability_summary_missing": 0,
        },
        "collections": {},
    }

    generated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    # Open quarantine outputs
    rej_no_qid_f = open(rejected_no_qid_path, "w", encoding="utf-8")
    rej_nonhuman_f = open(rejected_nonhuman_path, "w", encoding="utf-8")
    rej_outside_f = open(rejected_outside_path, "w", encoding="utf-8")

    try:
        for title in all_titles_list:
            wp = wp_meta.get(title)
            if not wp:
                continue

            qid = wp.get("wikibase_item")
            extract = (wp.get("extract") or "").strip()
            wp_url = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"

            if not qid:
                qa["counts"]["rejected_no_qid"] += 1
                rej_no_qid_f.write(json.dumps({
                    "title": title,
                    "wikipedia_url": wp_url,
                    "reason": "no_wikidata_qid",
                }, ensure_ascii=False) + "\n")
                continue

            qa["counts"]["candidates_with_qid"] += 1

            ent = entities.get(qid)
            if not ent:
                # rare, but quarantine as no_qid_effectively
                qa["counts"]["rejected_no_qid"] += 1
                rej_no_qid_f.write(json.dumps({
                    "title": title,
                    "wikidata_qid": qid,
                    "wikipedia_url": wp_url,
                    "reason": "qid_missing_in_wbgetentities",
                }, ensure_ascii=False) + "\n")
                continue

            # Human-only filter
            if not is_human(ent):
                qa["counts"]["rejected_nonhuman"] += 1
                rej_nonhuman_f.write(json.dumps({
                    "title": title,
                    "wikidata_qid": qid,
                    "wikipedia_url": wp_url,
                    "reason": "not_human_p31_not_q5",
                }, ensure_ascii=False) + "\n")
                continue

            # Build associations and determine inclusion
            assocs: List[dict] = []
            included = False
            reasons: List[str] = []

            for c in title_membership.get(title, []):
                assocs.append({
                    "type": c.association_type,
                    "label": c.association_label,
                    "start_year": c.window_start_year,
                    "end_year": c.window_end_year,
                    "evidence": {
                        "source": "collection_membership",
                        "text": f"Included via collection '{c.slug}'",
                        "ref": None,
                    }
                })
                if overlaps(cfg.target_start_year, cfg.target_end_year, c.window_start_year, c.window_end_year):
                    included = True
                    reasons.append(f"collection:{c.slug}")

            if not included:
                qa["counts"]["rejected_outside_window"] += 1
                rej_outside_f.write(json.dumps({
                    "title": title,
                    "wikidata_qid": qid,
                    "wikipedia_url": wp_url,
                    "reason": "no_association_overlaps_target_window",
                    "associations": assocs,
                }, ensure_ascii=False) + "\n")
                continue

            # Name
            name = ent.get("labels", {}).get("en", {}).get("value") or title

            # Vital events (single values)
            birth_time, birth_prec = get_time_claim(ent, "P569")
            death_time, death_prec = get_time_claim(ent, "P570")
            birth_place_qid = get_entity_claim(ent, "P19")
            death_place_qid = get_entity_claim(ent, "P20")

            birth = {
                "date": iso_date(birth_time),
                "precision": {"value": birth_prec, "label": precision_label(birth_prec)},
                "year": iso_year(birth_time),
                "place": {"name": place_labels.get(birth_place_qid), "wikidata_qid": birth_place_qid},
            }
            death = {
                "date": iso_date(death_time),
                "precision": {"value": death_prec, "label": precision_label(death_prec)},
                "year": iso_year(death_time),
                "place": {"name": place_labels.get(death_place_qid), "wikidata_qid": death_place_qid},
            }

            # Occupations
            occs = [occ_labels.get(oq, oq) for oq in get_entity_claims(ent, "P106", limit=10)]

            # Notability summary: Wikipedia extract; fallback to Wikidata description if extract missing
            wd_desc = ent.get("descriptions", {}).get("en", {}).get("value")
            notability_summary = extract or wd_desc or None

            record_id = f"wd:{qid}"

            rec = {
                "schema_version": "1.1",
                "id": record_id,
                "name": name,
                "wikipedia": {"title": title, "pageid": wp.get("pageid"), "url": wp_url},
                "wikidata": {"qid": qid},
                "birth": birth,
                "death": death,
                "occupations": occs,
                "massachusetts_associations": assocs,
                "notability": {
                    "summary": notability_summary,
                    "tags": [],
                    "evidence": {
                        "wikipedia_extract": extract or None,
                        "wikidata_description": wd_desc or None,
                        "occupations": occs,
                    },
                },
                "time_window": {
                    "included": True,
                    "rule": "event_association_overlaps_target_window",
                    "target_start_year": cfg.target_start_year,
                    "target_end_year": cfg.target_end_year,
                    "reasons": reasons,
                },
                "provenance": {
                    "generated_at_utc": generated_at,
                    "sources": [
                        {"type": "wikipedia", "value": "categorymembers|links|pageprops|extracts"},
                        {"type": "wikidata", "value": "wbgetentities(P31,P569,P19,P570,P20,P106)"},
                    ],
                    "config_schema_version": cfg.schema_version,
                },
            }

            # Merge/dedupe (QID id)
            if record_id in master_by_id:
                existing = master_by_id[record_id]
                seen = set((a["type"], a["label"], a.get("start_year"), a.get("end_year"))
                           for a in existing.get("massachusetts_associations", []))
                for a in rec["massachusetts_associations"]:
                    k = (a["type"], a["label"], a.get("start_year"), a.get("end_year"))
                    if k not in seen:
                        existing["massachusetts_associations"].append(a)
                        seen.add(k)

                # Fill missing summary if needed
                if not existing.get("notability", {}).get("summary") and rec["notability"]["summary"]:
                    existing["notability"]["summary"] = rec["notability"]["summary"]
            else:
                master_by_id[record_id] = rec

            # Add to per-collection view
            for c in title_membership.get(title, []):
                per_collection[c.slug].append(rec)

        # Write outputs
        master = sorted(master_by_id.values(), key=lambda r: (r.get("name") or "").lower())
        master_path = os.path.join(outdir, DEFAULT_MASTER_FILE)
        master_count = write_jsonl(master_path, master)
        qa["counts"]["included_master_records"] = master_count

        for c in cfg.collections:
            items = sorted(per_collection.get(c.slug, []), key=lambda r: (r.get("name") or "").lower())
            p = os.path.join(collections_dir, f"{c.slug}.jsonl")
            write_jsonl(p, items)
            qa["collections"][c.slug] = {
                "label": c.label,
                "records": len(items),
                "window": {"start_year": c.window_start_year, "end_year": c.window_end_year},
                "association": {"type": c.association_type, "label": c.association_label},
                "sources": [{"type": s.type, "title": s.title, "traverse_subcategories": s.traverse_subcategories} for s in c.sources],
            }

        # QA missingness (computed post-build)
        for r in master:
            if r["birth"]["date"] is None:
                qa["missingness_in_master"]["birth_date_missing"] += 1
            if r["birth"]["place"]["name"] is None and r["birth"]["place"]["wikidata_qid"] is None:
                qa["missingness_in_master"]["birth_place_missing"] += 1
            if r["death"]["date"] is None:
                qa["missingness_in_master"]["death_date_missing"] += 1
            if r["death"]["place"]["name"] is None and r["death"]["place"]["wikidata_qid"] is None:
                qa["missingness_in_master"]["death_place_missing"] += 1
            if r["notability"]["summary"] is None:
                qa["missingness_in_master"]["notability_summary_missing"] += 1

        # Manifest
        manifest = {
            "schema_version": "1.1",
            "target_window": {"start_year": cfg.target_start_year, "end_year": cfg.target_end_year},
            "master_file": DEFAULT_MASTER_FILE,
            "master_records": master_count,
            "collections": [
                {
                    "slug": c.slug,
                    "label": c.label,
                    "association": {"type": c.association_type, "label": c.association_label},
                    "window": {"start_year": c.window_start_year, "end_year": c.window_end_year},
                    "sources": [{"type": s.type, "title": s.title, "traverse_subcategories": s.traverse_subcategories} for s in c.sources],
                    "records": qa["collections"][c.slug]["records"],
                }
                for c in cfg.collections
            ],
        }
        write_json(os.path.join(outdir, "manifest.json"), manifest)

        # QA report
        write_json(os.path.join(outdir, "qa_report.json"), qa)

        print(f"Wrote {master_count} master records to {master_path}")
        print(f"Wrote QA report to {os.path.join(outdir, 'qa_report.json')}")
        print(f"Quarantine: {rejected_no_qid_path}, {rejected_nonhuman_path}, {rejected_outside_path}")

    finally:
        rej_no_qid_f.close()
        rej_nonhuman_f.close()
        rej_outside_f.close()


# ---------------------------
# Main
# ---------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Build MA notable people datasets (event-based; human-only; normalized).")
    ap.add_argument("--config", required=True, help="Path to collections config JSON (v2).")
    ap.add_argument("--outdir", default=DEFAULT_OUTDIR, help="Output directory.")
    ap.add_argument("--user-agent", default=DEFAULT_USER_AGENT, help="User-Agent string (set something identifiable).")
    ap.add_argument("--sleep", type=float, default=0.15, help="Sleep seconds between API calls.")
    args = ap.parse_args()

    cfg = load_config(args.config)
    api = ApiClient(user_agent=args.user_agent, sleep_s=args.sleep)

    build(api, cfg, args.outdir)


if __name__ == "__main__":
    main()
