#!/usr/bin/env python3
import argparse
import psycopg2
from pathlib import Path
from collections import defaultdict

def fetch_lines(conn, import_id):
    cur = conn.cursor()
    cur.execute("""
        SELECT line_id, parent_line_id, level, pointer, tag, value
        FROM gedcom_lines
        WHERE import_id = %s
        ORDER BY line_id
    """, (import_id,))
    rows = cur.fetchall()
    records = {}
    children_map = defaultdict(list)
    for row in rows:
        line_id, parent_id, level, pointer, tag, value = row
        records[line_id] = (level, pointer, tag, value)
        children_map[parent_id].append(line_id)
    return records, children_map

def write_gedcom(out_path, records, children_map):
    out_path.parent.mkdir(parents=True, exist_ok=True)  # 👈 Ensure directory exists

    def emit(line_id, output):
        level, pointer, tag, value = records[line_id]
        pointer_str = f"{pointer} " if pointer else ""
        value_str = f" {value}" if value else ""
        output.append(f"{level} {pointer_str}{tag}{value_str}")
        for child_id in children_map.get(line_id, []):
            emit(child_id, output)

    lines = []
    for root_id in children_map.get(None, []):
        emit(root_id, lines)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write('\ufeff')  # Write BOM for UTF-8
        f.write("\n".join(lines))
        f.write("\n")

def main():
    parser = argparse.ArgumentParser(description="Export GEDCOM file from DB.")
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
    records, children_map = fetch_lines(conn, args.import_id)
    print(f"✍️ Writing GEDCOM file to {args.out}...")
    write_gedcom(args.out, records, children_map)
    print(f"✅ Done. Exported {len(records)} lines.")

if __name__ == "__main__":
    main()
