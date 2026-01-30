#!/usr/bin/env python3
import argparse
import psycopg2

def main():
    parser = argparse.ArgumentParser(description="Backfill parent_line_id in gedcom_lines.")
    parser.add_argument("--import-id", type=int, required=True, help="Import ID to process")
    args = parser.parse_args()

    conn = psycopg2.connect(
        dbname="gedcom_db",
        user="gedcom_user",
        password="icecream",
        host="localhost"
    )
    cur = conn.cursor()

    cur.execute("""
        SELECT line_id, level FROM gedcom_lines
        WHERE import_id = %s
        ORDER BY line_num;
    """, (args.import_id,))
    rows = cur.fetchall()

    stack = []  # Will store tuples of (level, line_id)

    updates = []
    for line_id, level in rows:
        # Find parent (the last item in stack with level < current)
        parent_id = None
        while stack and stack[-1][0] >= level:
            stack.pop()
        if stack:
            parent_id = stack[-1][1]
        updates.append((parent_id, line_id))
        stack.append((level, line_id))

    cur.executemany("""
        UPDATE gedcom_lines SET parent_line_id = %s WHERE line_id = %s;
    """, updates)
    conn.commit()
    print(f"✅ Updated {len(updates)} parent_line_id entries for import_id={args.import_id}")

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
