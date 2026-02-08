#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple, NoReturn

import psycopg
from psycopg import sql as psql


def die(msg: str, code: int = 2) -> NoReturn:
    print(msg, file=sys.stderr)
    raise SystemExit(code)


def get_dsn() -> str:
    dsn = os.environ.get("GEDCOM_DB_DSN")
    if not dsn:
        die("GEDCOM_DB_DSN is not set. Example: postgresql://postgres:pw@127.0.0.1:5432/gedcom")
    return dsn


@dataclass(frozen=True)
class BatchItem:
    place_hash: str
    plac_raw: str


def parse_func_ident(func_name: str) -> psql.Composed:
    """
    Build a schema-qualified SQL identifier safely.
    Accepts:
      - geonames_candidates_hint_aware_v2   (assumes schema ged)
      - ged.geonames_candidates_hint_aware_v2
    """
    parts = [p.strip() for p in func_name.split(".") if p.strip()]
    if len(parts) == 1:
        return psql.SQL(".").join([psql.Identifier("ged"), psql.Identifier(parts[0])])
    if len(parts) == 2:
        return psql.SQL(".").join([psql.Identifier(parts[0]), psql.Identifier(parts[1])])
    die(f"Invalid function name: {func_name!r}. Use func or schema.func")


def ensure_session_settings(conn: psycopg.Connection, application_name: str) -> None:
    # Postgres doesn't reliably accept bind parameters in SET for psycopg (extended protocol),
    # but set_config() does.
    with conn.cursor() as cur:
        cur.execute("SELECT set_config('application_name', %s, false)", (application_name,))


def set_local_statement_timeout(conn: psycopg.Connection, seconds: int) -> None:
    # statement_timeout expects a string like '60000ms' or '60s'
    val = f"{int(seconds * 1000)}ms"
    with conn.cursor() as cur:
        cur.execute("SELECT set_config('statement_timeout', %s, true)", (val,))


def recover_working(conn: psycopg.Connection, run_id: str, older_than_minutes: int) -> int:
    q = """
    UPDATE ged.distinct_place_status
       SET status='new', last_error=NULL, attempted_at=NULL
     WHERE run_id=%s
       AND status='working'
       AND attempted_at IS NOT NULL
       AND attempted_at < now() - (%s || ' minutes')::interval
    """
    with conn.cursor() as cur:
        cur.execute(q, (run_id, older_than_minutes))
        return cur.rowcount


def clear_candidates(conn: psycopg.Connection, run_id: str) -> int:
    with conn.cursor() as cur:
        cur.execute("DELETE FROM ged.place_match_candidate_place WHERE run_id=%s", (run_id,))
        return cur.rowcount


def reset_status(conn: psycopg.Connection, run_id: str) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE ged.distinct_place_status
               SET status='new', attempted_at=NULL, last_error=NULL
             WHERE run_id=%s
            """,
            (run_id,),
        )
        return cur.rowcount


def fetch_batch(conn: psycopg.Connection, run_id: str, batch_size: int) -> List[BatchItem]:
    """
    Claim up to batch_size rows and mark them 'working'. Uses SKIP LOCKED.

    IMPORTANT:
      We must NOT include the materialized view in the FOR UPDATE locking query,
      otherwise Postgres errors: "cannot lock rows in materialized view ..."

    Strategy:
      1) lock + claim hashes from distinct_place_status only
      2) update those hashes to working
      3) join mv_distinct_places to fetch plac_raw for the claimed hashes
    """
    q = """
    WITH todo AS (
      SELECT dps.place_hash
        FROM ged.distinct_place_status dps
       WHERE dps.run_id = %s
         AND dps.status = 'new'
       ORDER BY dps.place_hash
       LIMIT %s
       FOR UPDATE SKIP LOCKED
    ),
    claimed AS (
      UPDATE ged.distinct_place_status dps
         SET status = 'working',
             attempted_at = now(),
             last_error = NULL
        FROM todo
       WHERE dps.run_id = %s
         AND dps.place_hash = todo.place_hash
      RETURNING dps.place_hash
    )
    SELECT c.place_hash, mdp.plac_raw
      FROM claimed c
      JOIN ged.mv_distinct_places mdp
        ON mdp.run_id = %s
       AND mdp.place_hash = c.place_hash
    ORDER BY c.place_hash
    """
    with conn.cursor() as cur:
        cur.execute(q, (run_id, batch_size, run_id, run_id))
        rows = cur.fetchall()
    return [BatchItem(place_hash=r[0], plac_raw=r[1]) for r in rows]


def mark_status(
    conn: psycopg.Connection,
    run_id: str,
    hashes: Sequence[str],
    status: str,
    last_error: Optional[str] = None,
) -> int:
    if not hashes:
        return 0
    q = """
    UPDATE ged.distinct_place_status
       SET status = %s,
           attempted_at = now(),
           last_error = %s
     WHERE run_id = %s
       AND place_hash = ANY(%s::text[])
    """
    with conn.cursor() as cur:
        cur.execute(q, (status, last_error, run_id, list(hashes)))
        return cur.rowcount


def mark_has_hits_no_hits(conn: psycopg.Connection, run_id: str, hashes: Sequence[str]) -> Tuple[int, int]:
    if not hashes:
        return 0, 0

    q_has = """
    UPDATE ged.distinct_place_status d
       SET status='has_hits',
           attempted_at=now(),
           last_error=NULL
     WHERE d.run_id=%s
       AND d.place_hash = ANY(%s::text[])
       AND EXISTS (
         SELECT 1
           FROM ged.place_match_candidate_place p
          WHERE p.run_id=d.run_id
            AND p.place_hash=d.place_hash
       )
    """
    q_no = """
    UPDATE ged.distinct_place_status d
       SET status='no_hits',
           attempted_at=now(),
           last_error=NULL
     WHERE d.run_id=%s
       AND d.place_hash = ANY(%s::text[])
       AND NOT EXISTS (
         SELECT 1
           FROM ged.place_match_candidate_place p
          WHERE p.run_id=d.run_id
            AND p.place_hash=d.place_hash
       )
    """
    with conn.cursor() as cur:
        cur.execute(q_has, (run_id, list(hashes)))
        has_ct = cur.rowcount
        cur.execute(q_no, (run_id, list(hashes)))
        no_ct = cur.rowcount
    return has_ct, no_ct


def insert_candidates_distinct(
    conn: psycopg.Connection,
    run_id: str,
    batch: Sequence[BatchItem],
    per_place: int,
    function_name: str,
) -> int:
    if not batch:
        return 0

    func_ident = parse_func_ident(function_name)

    place_hashes = [b.place_hash for b in batch]
    plac_raws = [b.plac_raw for b in batch]

    q = psql.SQL(
        """
        WITH batch AS (
          SELECT *
            FROM unnest(%(hashes)s::text[], %(raws)s::text[])
                 AS t(place_hash, plac_raw)
        ),
        candidates AS (
          SELECT
            %(run_id)s::uuid AS run_id,
            b.place_hash,
            b.plac_raw,
            c.geonameid,
            c.rank_score::numeric(6,3) AS score,
            jsonb_build_object(
              'base_score', c.base_score,
              'rank_score', c.rank_score
            ) AS reasons
          FROM batch b
          CROSS JOIN LATERAL {func}(b.plac_raw, %(limit)s::int) AS c
        )
        INSERT INTO ged.place_match_candidate_place
          (run_id, place_hash, plac_raw, geonameid, score, reasons)
        SELECT run_id, place_hash, plac_raw, geonameid, score, reasons
          FROM candidates
        ON CONFLICT (run_id, place_hash, geonameid) DO UPDATE
          SET score = EXCLUDED.score,
              reasons = EXCLUDED.reasons,
              created_at = now()
        RETURNING 1
        """
    ).format(func=func_ident)

    with conn.cursor() as cur:
        cur.execute(
            q,
            {"run_id": run_id, "hashes": place_hashes, "raws": plac_raws, "limit": per_place},
        )
        rows = cur.fetchall()
        return len(rows)


def get_status_counts(conn: psycopg.Connection, run_id: str) -> str:
    q = """
    SELECT
      count(*) FILTER (WHERE status='new')      AS new,
      count(*) FILTER (WHERE status='working')  AS working,
      count(*) FILTER (WHERE status='has_hits') AS has_hits,
      count(*) FILTER (WHERE status='no_hits')  AS no_hits,
      count(*) FILTER (WHERE status='error')    AS error
    FROM ged.distinct_place_status
    WHERE run_id=%s
    """
    with conn.cursor() as cur:
        cur.execute(q, (run_id,))
        (new, working, has_hits, no_hits, error) = cur.fetchone()
    return f"status[new={new} working={working} has_hits={has_hits} no_hits={no_hits} error={error}]"


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate GeoNames candidates per DISTINCT place into ged.place_match_candidate_place.\n\n"
            "Example:\n"
            r"  python -u .\src\generate_candidates.py --run-id <uuid> --batch-size 500 --per-place 10 "
            r"--function geonames_candidates_hint_aware_v2"
            "\n"
        )
    )
    parser.add_argument("--run-id", required=True, help="UUID run_id")
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--per-place", type=int, default=10)
    parser.add_argument(
        "--function",
        default="geonames_candidates_hint_aware",
        help="SQL function to call (default schema ged). e.g. geonames_candidates_hint_aware_v2",
    )
    parser.add_argument("--max-batches", type=int, default=0, help="Stop after N batches (0=run until done)")
    parser.add_argument(
        "--statement-timeout-seconds",
        type=int,
        default=180,
        help="Cancel any single batch that runs longer than this",
    )
    parser.add_argument("--reset", action="store_true", help="Reset all statuses to 'new' for this run")
    parser.add_argument("--clear-candidates", action="store_true", help="Delete existing candidates for this run")
    parser.add_argument(
        "--recover-working",
        type=int,
        default=0,
        metavar="MINUTES",
        help="Reset 'working' back to 'new' if attempted_at older than MINUTES",
    )

    args = parser.parse_args(argv)
    dsn = get_dsn()

    with psycopg.connect(dsn, autocommit=False) as conn:
        ensure_session_settings(conn, application_name="generate_candidates.py")

        if args.recover_working > 0:
            n = recover_working(conn, args.run_id, args.recover_working)
            conn.commit()
            print(f"Recovered {n} stale 'working' rows back to 'new' (older than {args.recover_working} min)")

        if args.clear_candidates:
            n = clear_candidates(conn, args.run_id)
            conn.commit()
            print(f"Cleared {n} candidate rows from ged.place_match_candidate_place for run {args.run_id}")

        if args.reset:
            n = reset_status(conn, args.run_id)
            conn.commit()
            print(f"Reset {n} rows in ged.distinct_place_status to status='new' for run {args.run_id}")

        batch_no = 0
        tot_places = 0
        tot_inserted = 0

        while True:
            if args.max_batches and batch_no >= args.max_batches:
                print("Stopped early due to --max-batches")
                break

            conn.rollback()
            batch = fetch_batch(conn, args.run_id, args.batch_size)
            if not batch:
                conn.rollback()
                break

            batch_no += 1
            tot_places += len(batch)
            hashes = [b.place_hash for b in batch]

            print(f"Starting batch {batch_no} (places={len(batch)})...")
            t0 = time.time()

            try:
                # set per-batch statement timeout safely (no SET LOCAL with bind params)
                set_local_statement_timeout(conn, args.statement_timeout_seconds)

                inserted = insert_candidates_distinct(
                    conn=conn,
                    run_id=args.run_id,
                    batch=batch,
                    per_place=args.per_place,
                    function_name=args.function,
                )
                mark_has_hits_no_hits(conn, args.run_id, hashes)
                conn.commit()

            except Exception as ex:
                conn.rollback()
                try:
                    mark_status(conn, args.run_id, hashes, "error", last_error=str(ex)[:900])
                    conn.commit()
                except Exception:
                    conn.rollback()
                dt = time.time() - t0
                print(f"ERROR in batch {batch_no} after {dt:0.1f}s: {ex}")
                continue

            dt = time.time() - t0
            tot_inserted += inserted
            print(
                f"Batch {batch_no}: places={len(batch)} inserted={inserted} "
                f"tot_places={tot_places} tot_inserted={tot_inserted} "
                f"{get_status_counts(conn, args.run_id)} time={dt:0.1f}s"
            )

        print(
            f"Done. batches={batch_no} tot_places={tot_places} tot_inserted={tot_inserted} "
            f"{get_status_counts(conn, args.run_id)}"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
