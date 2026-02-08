BEGIN;

-- one row per distinct place string (per run)
CREATE TABLE IF NOT EXISTS ged.distinct_place_status (
  run_id uuid NOT NULL,
  place_hash text NOT NULL,
  plac_raw text NOT NULL,
  status text NOT NULL DEFAULT 'new',  -- new|attempted|no_hits|has_hits|error
  attempted_at timestamptz NULL,
  last_error text NULL,
  PRIMARY KEY (run_id, place_hash)
);

-- seed it from the materialized view (idempotent)
INSERT INTO ged.distinct_place_status (run_id, place_hash, plac_raw)
SELECT run_id, place_hash, plac_raw
FROM ged.mv_distinct_places
ON CONFLICT (run_id, place_hash) DO NOTHING;

CREATE INDEX IF NOT EXISTS ix_distinct_place_status_run_status
  ON ged.distinct_place_status(run_id, status);

COMMIT;
