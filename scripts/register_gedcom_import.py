#!/usr/bin/env python3
import argparse
import hashlib
import psycopg2
from pathlib import Path

def compute_hash(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True, type=Path, help="Path to .ged or enriched .json file")
    args = parser.parse_args()

    file_hash = compute_hash(args.file)
    conn = psycopg2.connect(
        dbname="gedcom_db",
        user="gedcom_user",
        password="icecream",
        host="localhost"
    )
    cur = conn.cursor()

    cur.execute("SELECT import_id FROM gedcom_imports WHERE file_hash = %s", (file_hash,))
    existing = cur.fetchone()
    if existing:
        print(f"⚠️ Already imported: import_id={existing[0]}")
        return

    cur.execute("""
        INSERT INTO gedcom_imports (filename, file_hash)
        VALUES (%s, %s)
        RETURNING import_id;
    """, (args.file.name, file_hash))
    import_id = cur.fetchone()[0]
    conn.commit()
    print(f"✅ Registered import_id={import_id} for {args.file.name}")

if __name__ == "__main__":
    main()
