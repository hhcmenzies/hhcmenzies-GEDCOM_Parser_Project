#!/usr/bin/env python3
import argparse, json, re, sys
from pathlib import Path
from typing import Any, Dict, Optional

ARTIFACT_RE = re.compile(r":contentReference\[[^\]]+\]\{[^}]+\}")

def clean_str(v: Any) -> Any:
    if isinstance(v, str):
        v = ARTIFACT_RE.sub("", v)
        return v.strip()
    return v

def normalize_obj(o: Any) -> Any:
    if isinstance(o, dict):
        return {k: normalize_obj(clean_str(v)) for k, v in o.items()}
    if isinstance(o, list):
        return [normalize_obj(clean_str(v)) for v in o]
    return clean_str(o)

def split_name(full: Optional[str]) -> Dict[str, Optional[str]]:
    full = (full or "").strip()
    if not full:
        return {"full": None, "given": None, "surname": None, "aliases": []}
    parts = full.split()
    if len(parts) == 1:
        return {"full": full, "given": full, "surname": None, "aliases": []}
    return {"full": full, "given": " ".join(parts[:-1]), "surname": parts[-1], "aliases": []}

def as_int(v: Any) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(str(v).strip())
    except Exception:
        return None

def year_only(year: Any) -> Dict[str, Any]:
    y = as_int(year)
    return {"date": None, "year": y, "precision": "year" if y is not None else None}

def place_obj(raw: Any) -> Optional[Dict[str, Any]]:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    return {"raw": s, "name": None, "qid": None}

def pick(rec: Dict[str, Any], *keys: str) -> Any:
    for k in keys:
        if k in rec and rec[k] not in (None, "", []):
            return rec[k]
    return None

def build_record(rec: Dict[str, Any], dataset_slug: str, assoc_label: str) -> Dict[str, Any]:
    rec = normalize_obj(rec)
    full = pick(rec, "Full Name", "full_name", "name", "Name", "person", "Person")
    nm = split_name(full if isinstance(full, str) else None)

    by = pick(rec, "Birth Year", "birth_year", "Birth", "birthYear", "birth")
    dy = pick(rec, "Death Year", "death_year", "Death", "deathYear", "death")
    bp = pick(rec, "Birth Location", "birth_location", "birthPlace", "birth_place", "Birthplace", "Birth Place")
    dp = pick(rec, "Death Location", "death_location", "deathPlace", "death_place", "Deathplace", "Death Place")

    notes = []
    for key in ("Occupation", "Role", "Trial Status", "Additional metadata", "Metadata", "Notes", "note"):
        val = rec.get(key)
        if isinstance(val, str) and val.strip():
            notes.append({"label": key, "text": val.strip()})
        elif val not in (None, "", [], {}):
            notes.append({"label": key, "text": json.dumps(val, ensure_ascii=False)})

    stable_id = nm.get("full") or "unknown"
    stable_id = re.sub(r"\s+", "_", stable_id.strip())
    stable_id = re.sub(r"[^A-Za-z0-9_\-\.]", "", stable_id)[:120] or "unknown"

    out = {
        "id": f"legacy:{dataset_slug}:{stable_id}",
        "name": nm,
        "wikidata": {"qid": None},
        "wikipedia": {"title": None, "url": None},
        "birth": {**year_only(by), "place": place_obj(bp)},
        "death": {**year_only(dy), "place": place_obj(dp)},
        "occupations": [],
        "associations": [{"type": "event_in", "label": assoc_label, "collection": dataset_slug}],
        "notes": notes,
        "provenance": {
            "source_dataset": dataset_slug,
            "sources": [{"type": "import", "ref": "legacy_json"}],
            "raw": rec
        }
    }
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", required=True)
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", dest="out_path", required=True)
    args = ap.parse_args()

    inp = Path(args.in_path)
    data = json.loads(inp.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise SystemExit(f"Input must be a JSON array, got {type(data).__name__}")

    outp = Path(args.out_path)
    outp.parent.mkdir(parents=True, exist_ok=True)

    n = 0
    with outp.open("w", encoding="utf-8") as f:
        for rec in data:
            if not isinstance(rec, dict):
                continue
            o = build_record(rec, args.dataset, args.label)
            f.write(json.dumps(o, ensure_ascii=False) + "\n")
            n += 1

    print(f"Wrote {n} records -> {outp}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("ERROR:", e, file=sys.stderr)
        sys.exit(2)
