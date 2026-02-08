CREATE MATERIALIZED VIEW IF NOT EXISTS ged.mv_distinct_places AS
SELECT
  run_id,
  place_hash,
  plac_raw,
  form_raw,
  count(*) AS occurrences
FROM ged.place_occurrence
GROUP BY run_id, place_hash, plac_raw, form_raw;

CREATE INDEX IF NOT EXISTS ix_mv_distinct_places_run
  ON ged.mv_distinct_places(run_id);

CREATE INDEX IF NOT EXISTS ix_mv_distinct_places_plac_trgm
  ON ged.mv_distinct_places USING gin (plac_raw gin_trgm_ops);
