#!/usr/bin/env python3
import argparse
import re
import psycopg2
from pathlib import Path

LINE_PATTERN = re.compile(r"^(\d+)\s+(@[^@]+@)?\s*([A-Z0-9_]+)(?:\s+(.*))?$")

def parse_line(raw):
    raw = raw.lstrip('\ufeff')  # Strip BOM
    match = LINE_PATTERN.match(raw)
    if not match:
        return None
    level, pointer, tag, value = match.groups()
    return int(level), (pointer or "").strip(), tag.strip(), (value or "").strip()

def main():
    parser = argparse.ArgumentParser(description="Load GEDCOM lines into database.")
    parser.add_argument("--file", required=True, type=Path)
    parser.add_argument("--import-id", required=True, type=int)
    args = parser.parse_args()

    conn = psycopg2.connect(
        dbname="gedcom_db", user="gedcom_user", password="icecream", host="localhost",
        options="-c client_encoding=UTF8"
    )
    cur = conn.cursor()

    with args.file.open("r", encoding="utf-8") as f:
        for line_num, raw_line in enumerate(f, 1):
            parsed = parse_line(raw_line.strip())
            if parsed is None:
                print(f"⚠️ Skipping unparseable line {line_num}: {raw_line.strip()}")
                continue
            level, pointer, tag, value = parsed
            cur.execute("""
                INSERT INTO gedcom_lines (import_id, line_num, level, pointer, tag, value)
                VALUES (%s, %s, %s, %s, %s, %s);
            """, (args.import_id, line_num, level, pointer or None, tag, value))

    conn.commit()
    cur.close()
    conn.close()
    print(f"✅ GEDCOM lines loaded for import_id={args.import_id} from {args.file.name}")

if __name__ == "__main__":
    main()
