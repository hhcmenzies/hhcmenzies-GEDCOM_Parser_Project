#!/usr/bin/env python3
import argparse
import psycopg2
import json
from pathlib import Path
from collections import defaultdict

def fetch_lines(conn, import_id):
    cur = conn.cursor()
    cur.execute("""
        SELECT line_id, parent_line_id, level, xref_id, tag, value
        FROM gedcom_lines
        WHERE import_id = %s
        ORDER BY line_id
    """, (import_id,))
    rows = cur.fetchall()
    records = {}
    children_map = defaultdict(list)
    for row in rows:
        line_id, parent_id, level, xref_id, tag, value = row
        records[line_id] = {
            "line_id": line_id,
            "level": level,
            "xref": xref_id,
            "tag": tag,
            "value": value,
            "children": []
        }
        children_map[parent_id].append(line_id)

    # Attach children to parents
    for parent_id, child_ids in children_map.items():
        if parent_id in records:
            for cid in child_ids:
                records[parent_id]["children"].append(records[cid])

    # Top-level records have parent_id = None
    return [records[rid] for rid in children_map[None]]

def main():
    parser = argparse.ArgumentParser(description="Export structured GEDCOM records to JSON.")
    parser.add_argument("--import-id", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    conn = psycopg2.connect(
        dbname="gedcom_db",
        user="gedcom_user",
        password="icecream",
        host="localhost"
    )

    print(f"📥 Fetching structured records for import_id={args.import_id}...")
    records = fetch_lines(conn, args.import_id)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

    print(f"✅ Done. Exported {len(records)} root-level records to {args.out}")

if __name__ == "__main__":
    main()
