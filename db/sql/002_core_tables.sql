-- db/sql/002_core_tables.sql

-- Final table: store *occurrences* (not unique places)
CREATE TABLE IF NOT EXISTS ged.place_occurrence (
  place_occurrence_id BIGSERIAL PRIMARY KEY,

  -- provenance / batching
  run_id UUID NOT NULL,
  source_file_id TEXT NULL,
  source_path TEXT NULL,

  -- GEDCOM provenance
  record_xref TEXT NULL,         -- @I123@ or @F45@
  record_type TEXT NULL,         -- INDI/FAM/etc
  event_type TEXT NULL,          -- BIRT/DEAT/MARR/RESI/EVEN/...
  event_date TEXT NULL,          -- raw

  -- GEDCOM PLAC payload
  plac_raw TEXT NOT NULL,
  form_raw TEXT NULL,
  lati_raw TEXT NULL,
  long_raw TEXT NULL,

  -- helper
  place_hash TEXT GENERATED ALWAYS AS (
    md5(coalesce(plac_raw,'') || '|' || coalesce(form_raw,''))
  ) STORED,

  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Helpful indexes (not uniqueness)
CREATE INDEX IF NOT EXISTS ix_place_occurrence_run_id
  ON ged.place_occurrence(run_id);

CREATE INDEX IF NOT EXISTS ix_place_occurrence_plac_raw_trgm
  ON ged.place_occurrence USING gin (plac_raw gin_trgm_ops);

CREATE INDEX IF NOT EXISTS ix_place_occurrence_place_hash
  ON ged.place_occurrence(place_hash);

-- Staging table: raw CSV load target (no generated columns)
CREATE TABLE IF NOT EXISTS ged.place_occurrence_stage (
  run_id UUID NOT NULL,
  source_file_id TEXT NULL,
  source_path TEXT NULL,
  record_xref TEXT NULL,
  record_type TEXT NULL,
  event_type TEXT NULL,
  event_date TEXT NULL,
  plac_raw TEXT NOT NULL,
  form_raw TEXT NULL,
  lati_raw TEXT NULL,
  long_raw TEXT NULL
);

-- Candidate / resolution tables (as you already have)
CREATE TABLE IF NOT EXISTS ged.place_match_candidate (
  place_occurrence_id BIGINT NOT NULL
    REFERENCES ged.place_occurrence(place_occurrence_id) ON DELETE CASCADE,
  geonameid INTEGER NOT NULL
    REFERENCES geonames.allcountries(geonameid),
  score NUMERIC(6,3) NOT NULL,
  reasons JSONB NULL,
  PRIMARY KEY (place_occurrence_id, geonameid)
);

CREATE TABLE IF NOT EXISTS ged.place_resolution (
  place_occurrence_id BIGINT PRIMARY KEY
    REFERENCES ged.place_occurrence(place_occurrence_id) ON DELETE CASCADE,
  geonameid_selected INTEGER NULL
    REFERENCES geonames.allcountries(geonameid),
  resolution_method TEXT NOT NULL DEFAULT 'unresolved',
  confidence NUMERIC(4,3) NULL,
  notes TEXT NULL,
  resolved_at TIMESTAMPTZ NULL
);
