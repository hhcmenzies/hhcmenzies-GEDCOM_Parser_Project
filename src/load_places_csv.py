import argparse
import csv
from pathlib import Path
from typing import Optional, Set

import psycopg


STAGE_COPY_SQL = """
COPY ged.place_occurrence_stage (
    run_id, source_file_id, source_path, record_xref, record_type,
    event_type, event_date, plac_raw, form_raw, lati_raw, long_raw
)
FROM STDIN WITH (FORMAT csv, HEADER true);
"""

DELETE_EXISTING_SQL = """
DELETE FROM ged.place_occurrence
WHERE run_id = ANY(%s);
"""

INSERT_FINAL_SQL = """
INSERT INTO ged.place_occurrence (
    run_id, source_file_id, source_path, record_xref, record_type,
    event_type, event_date, plac_raw, form_raw, lati_raw, long_raw
)
SELECT
    run_id, source_file_id, source_path, record_xref, record_type,
    event_type, event_date, plac_raw, form_raw, lati_raw, long_raw
FROM ged.place_occurrence_stage;
"""

TRUNCATE_STAGE_SQL = "TRUNCATE TABLE ged.place_occurrence_stage;"


def infer_run_ids_from_csv(csv_path: Path) -> Set[str]:
    """Reads run_id values from the CSV header+first N rows safely."""
    run_ids: Set[str] = set()
    with csv_path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or "run_id" not in reader.fieldnames:
            raise ValueError("CSV is missing required column: run_id")

        # Read up to 10k rows for run_id set; usually it's 1 run_id anyway.
        for i, row in enumerate(reader):
            rid = (row.get("run_id") or "").strip()
            if rid:
                run_ids.add(rid)
            if i >= 10000:
                break

    if not run_ids:
        raise ValueError("Could not find any run_id values in CSV.")
    return run_ids


def load_csv(csv_path: Path, dsn: str, wipe_existing_runs: bool = True) -> None:
    if not csv_path.exists():
        raise FileNotFoundError(f"--csv not found: {csv_path}")

    run_ids = infer_run_ids_from_csv(csv_path)
    run_id_list = sorted(run_ids)

    with psycopg.connect(dsn) as conn:
        conn.execute("SET statement_timeout = '0';")
        conn.execute("SET lock_timeout = '0';")

        with conn.cursor() as cur:
            # 1) Clear stage
            cur.execute(TRUNCATE_STAGE_SQL)

            # 2) COPY into stage
            with cur.copy(STAGE_COPY_SQL) as copy:
                with csv_path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
                    for line in f:
                        copy.write(line)

            # 3) Idempotent: delete existing rows for these run_id(s)
            if wipe_existing_runs:
                cur.execute(DELETE_EXISTING_SQL, (run_id_list,))

            # 4) Insert from stage into final
            cur.execute(INSERT_FINAL_SQL)

        conn.commit()

    print(f"Loaded CSV: {csv_path}")
    print(f"Run ID(s): {', '.join(run_id_list)}")


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Load place_occurrence CSV into Postgres safely via staging.")
    parser.add_argument("--csv", required=True, help="Path to reports/place_occurrence.csv")
    parser.add_argument("--dsn", default=None, help="Postgres DSN. If omitted, uses env GEDCOM_DB_DSN.")
    parser.add_argument("--no-wipe", action="store_true", help="Do NOT delete existing rows for run_id(s) in the CSV.")
    args = parser.parse_args(argv)

    dsn = args.dsn or (Path().env if False else None)  # keeps type-checkers quiet
    dsn = args.dsn or __import__("os").environ.get("GEDCOM_DB_DSN")
    if not dsn:
        raise SystemExit("Missing DSN. Set GEDCOM_DB_DSN or pass --dsn.")

    load_csv(Path(args.csv), dsn, wipe_existing_runs=not args.no_wipe)


if __name__ == "__main__":
    main()
