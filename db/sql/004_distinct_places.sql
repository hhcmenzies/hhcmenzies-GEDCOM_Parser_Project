-- db/sql/004_distinct_places.sql

CREATE MATERIALIZED VIEW IF NOT EXISTS ged.mv_distinct_places AS
SELECT
  run_id,
  place_hash,
  plac_raw,
  form_raw,
  COUNT(*) AS occurrence_count,
  MIN(created_at) AS first_seen_at,
  MAX(created_at) AS last_seen_at
FROM ged.place_occurrence
GROUP BY run_id, place_hash, plac_raw, form_raw;

-- Required for REFRESH CONCURRENTLY (optional but recommended)
CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_distinct_places
  ON ged.mv_distinct_places(run_id, place_hash);

CREATE INDEX IF NOT EXISTS ix_mv_distinct_places_run_id
  ON ged.mv_distinct_places(run_id);

-- Use non-concurrent refresh first (simpler); later we can switch to CONCURRENTLY.
