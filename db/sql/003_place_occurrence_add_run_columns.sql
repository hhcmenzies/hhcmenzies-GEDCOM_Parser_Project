-- db/sql/003_place_occurrence_add_run_columns.sql

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Add columns present in CSV but missing in table
ALTER TABLE ged.place_occurrence
  ADD COLUMN IF NOT EXISTS run_id uuid,
  ADD COLUMN IF NOT EXISTS source_path text,
  ADD COLUMN IF NOT EXISTS record_type text;

-- Backfill (safe defaults for any existing rows; you currently have 0 rows)
UPDATE ged.place_occurrence
SET
  run_id = COALESCE(run_id, gen_random_uuid()),
  source_path = COALESCE(source_path, source_file_id),
  record_type = COALESCE(record_type, 'UNKNOWN')
WHERE run_id IS NULL OR source_path IS NULL OR record_type IS NULL;

-- Make run_id required going forward
ALTER TABLE ged.place_occurrence
  ALTER COLUMN run_id SET NOT NULL;

-- IMPORTANT: Your original unique index was global (place_hash).
-- That prevents re-loading the same place strings in a *new run*.
-- We want dedupe PER RUN, so drop the old and replace it.

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM pg_indexes
    WHERE schemaname='ged' AND indexname='ux_place_occurrence_hash'
  ) THEN
    EXECUTE 'DROP INDEX ged.ux_place_occurrence_hash';
  END IF;
END$$;

CREATE UNIQUE INDEX IF NOT EXISTS ux_place_occurrence_run_hash
  ON ged.place_occurrence(run_id, place_hash);

-- Helpful query index for per-run exploration
CREATE INDEX IF NOT EXISTS ix_place_occurrence_run_id
  ON ged.place_occurrence(run_id);

COMMIT;
