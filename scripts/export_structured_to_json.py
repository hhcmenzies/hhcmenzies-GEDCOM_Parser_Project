#!/usr/bin/env python3
import argparse
import json
import psycopg2
from collections import defaultdict
from pathlib import Path

def fetch_lines(conn, import_id):
    cur = conn.cursor()
    cur.execute("""
        SELECT line_id, parent_line_id, level, xref_id, tag, value
        FROM gedcom_lines
        WHERE import_id = %s
        ORDER BY line_id
    """, (import_id,))
    return cur.fetchall()

def build_tree(lines):
    nodes = {}
    children_map = defaultdict(list)

    for line in lines:
        line_id, parent_id, level, xref, tag, value = line
        node = {
            "level": level,
            "xref": xref,
            "tag": tag,
            "value": value,
            "children": []
        }
        nodes[line_id] = node
        children_map[parent_id].append(line_id)

    def attach_children(parent_id):
        return [nodes[cid] | {"children": attach_children(cid)} for cid in children_map.get(parent_id, [])]

    return attach_children(None)

def main():
    parser = argparse.ArgumentParser(description="Export structured GEDCOM JSON from database.")
    parser.add_argument("--import-id", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    conn = psycopg2.connect(
        dbname="gedcom_db",
        user="gedcom_user",
        password="icecream",
        host="localhost"
    )

    print(f"📥 Fetching lines for import_id={args.import_id}...")
    lines = fetch_lines(conn, args.import_id)

    print("🌳 Building structured tree...")
    tree = build_tree(lines)

    print(f"💾 Writing to {args.out}...")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        json.dump(tree, f, indent=2, ensure_ascii=False)

    print(f"✅ Done. Wrote {len(tree)} root records to {args.out}")

if __name__ == "__main__":
    main()
