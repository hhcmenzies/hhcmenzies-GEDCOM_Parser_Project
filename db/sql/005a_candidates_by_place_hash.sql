BEGIN;

-- Store candidates per DISTINCT place (run_id + place_hash), not per occurrence row
CREATE TABLE IF NOT EXISTS ged.place_candidates (
  run_id uuid NOT NULL,
  place_hash text NOT NULL,
  plac_raw text NOT NULL,
  geonameid int NOT NULL REFERENCES geonames.allcountries(geonameid),
  score numeric(6,3) NOT NULL,
  reasons jsonb NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (run_id, place_hash, geonameid)
);

CREATE INDEX IF NOT EXISTS ix_place_candidates_run_hash
  ON ged.place_candidates(run_id, place_hash);

COMMIT;
