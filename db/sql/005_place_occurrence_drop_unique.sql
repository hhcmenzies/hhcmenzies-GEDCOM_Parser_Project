BEGIN;

-- place_occurrence must allow duplicates (it stores occurrences)
DROP INDEX IF EXISTS ged.ux_place_occurrence_run_hash;

-- keep it indexed for grouping / joins
CREATE INDEX IF NOT EXISTS ix_place_occurrence_run_hash
  ON ged.place_occurrence (run_id, place_hash);

COMMIT;
