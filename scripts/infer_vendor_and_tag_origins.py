#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
from collections import defaultdict

def norm(x): return str(x).strip().upper()

def read_json(p: Path): 
    with p.open("r", encoding="utf-8") as f: 
        return json.load(f)

def infer_vendor(head_sour: str) -> str:
    val = head_sour.lower()
    if "ancestry" in val: return "Ancestry.com"
    if "family tree maker" in val or "ftm" in val: return "Family Tree Maker"
    if "myheritage" in val: return "MyHeritage"
    if "gedmatch" in val: return "GEDmatch"
    if "rootsmagic" in val: return "RootsMagic"
    return "Unknown"

def main():
    ap = argparse.ArgumentParser(description="Infer vendor origin from HEAD.SOUR and classify tags.")
    ap.add_argument("--enriched", required=True, type=Path)
    ap.add_argument("--raw-report", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    enriched = read_json(args.enriched)
    raw = read_json(args.raw_report)

    vendor = infer_vendor(raw.get("inputs", {}).get("head_sour", "Unknown"))
    standard = set(raw.get("stats", {}).get("standard_tags", []))
    custom = set(raw.get("stats", {}).get("custom_tags", []))

    tag_counts = defaultdict(int)
    for rec in enriched:
        tag = norm(rec.get("tag", ""))
        tag_counts[tag] += 1

    print(f"\n🧩 Inferred Vendor: {vendor}")
    print(f"Total Tags: {len(tag_counts)}")
    print(f"Standard Tags ({len(standard)}): {sorted(standard)}")
    print(f"Custom Tags ({len(custom)}): {sorted(custom)}\n")

    print("📊 Tag Counts:")
    for t, c in sorted(tag_counts.items()):
        prefix = "CUSTOM" if t in custom or t.startswith("_") else "STANDARD"
        print(f"{prefix:<8} {t:<10} {c:>5}")

    output = {
        "vendor": vendor,
        "tag_counts": dict(tag_counts),
        "standard_tags": sorted(standard),
        "custom_tags": sorted(custom)
    }
    with args.out.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n✅ Wrote vendor inference report: {args.out}")

if __name__ == "__main__":
    main()
