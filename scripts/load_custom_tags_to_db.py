#!/usr/bin/env python3
import argparse, json
import psycopg2
from pathlib import Path

def norm(x): return str(x).strip().upper()

def main():
    parser = argparse.ArgumentParser(description="Load custom tag counts into PostgreSQL")
    parser.add_argument("--custom-tag-report", required=True, type=Path, help="Path to custom_tags_report JSON")
    args = parser.parse_args()

    with args.custom_tag_report.open("r", encoding="utf-8") as f:
        report = json.load(f)

    custom_tags = report.get("custom_tags", {})
    if not custom_tags:
        print("❌ No custom tags found in report.")
        return

    conn = psycopg2.connect(
        dbname="gedcom_db",
        user="gedcom_user",
        password="icecream",
        host="localhost",
        options="-c client_encoding=UTF8"
    )
    cur = conn.cursor()

    inserted, skipped = 0, 0
    for tag, count in custom_tags.items():
        tag_clean = norm(tag)
        try:
            cur.execute("""
                INSERT INTO custom_tags (import_id, owner_type, owner_xref, tag, value, count)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (import_id, tag) DO UPDATE
                  SET count = EXCLUDED.count;
            """, (1, 'UNKNOWN', 'UNKNOWN', tag_clean, None, count))
            inserted += 1
        except Exception as e:
            print(f"⚠️  Failed to insert tag '{tag_clean}': {e}")
            skipped += 1

    conn.commit()
    cur.close()
    conn.close()
    print(f"✅ Done. Inserted/Updated {inserted} tags. Skipped {skipped}.")

if __name__ == "__main__":
    main()
