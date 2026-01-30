#!/usr/bin/env python3
import argparse
import json
import psycopg2
from pathlib import Path
from collections import defaultdict

def fetch_lines(conn, import_id):
    cur = conn.cursor()
    cur.execute("""
        SELECT line_id, level, xref_id, tag, value
        FROM gedcom_lines
        WHERE import_id = %s
        ORDER BY line_num
    """, (import_id,))
    return cur.fetchall()

def build_tree(lines):
    stack = []
    root_records = []

    id_to_node = {}

    for line_id, level, xref_id, tag, value in lines:
        node = {
            "line_id": line_id,
            "xref_id": xref_id,
            "tag": tag,
            "value": value,
            "children": []
        }
        id_to_node[line_id] = node

        while stack and stack[-1][0] >= level:
            stack.pop()

        if stack:
            parent_node = stack[-1][1]
            parent_node["children"].append(node)
        else:
            root_records.append(node)

        stack.append((level, node))

    return root_records

def main():
    parser = argparse.ArgumentParser(description="Build structured records from GEDCOM lines.")
    parser.add_argument("--import-id", required=True, type=int, help="Import ID from gedcom_imports")
    parser.add_argument("--out", required=True, type=Path, help="Output JSON file path")
    args = parser.parse_args()

    conn = psycopg2.connect(dbname="gedcom_db", user="gedcom_user", password="icecream", host="localhost")
    lines = fetch_lines(conn, args.import_id)
    records = build_tree(lines)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)

    print(f"✅ Wrote {len(records)} root-level records to {args.out}")

if __name__ == "__main__":
    main()
