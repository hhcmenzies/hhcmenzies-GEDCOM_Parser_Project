-- db/sql/001_places_ingest.sql

-- 1) Extensions used
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS pgcrypto;  -- for gen_random_uuid()

-- 2) Dedicated schema
CREATE SCHEMA IF NOT EXISTS ged;

-- 3) Place occurrences (ingest target)
CREATE TABLE IF NOT EXISTS ged.place_occurrence (
  place_occurrence_id BIGSERIAL PRIMARY KEY,

  -- provenance
  run_id uuid NOT NULL DEFAULT gen_random_uuid(),
  source_file_id TEXT NULL,             -- usually the GEDCOM file name
  source_path TEXT NULL,                -- optional: full path or relative path
  record_xref TEXT NULL,                -- @I123@ / @F45@ etc
  record_type TEXT NULL,                -- INDI/FAM/etc if you choose to track it
  event_type TEXT NULL,                 -- BIRT/DEAT/MARR/RESI/EVEN/etc
  event_date TEXT NULL,                 -- raw GEDCOM date

  -- GEDCOM PLAC payload
  plac_raw TEXT NOT NULL,
  form_raw TEXT NULL,                   -- PLAC.FORM (optional)
  lati_raw TEXT NULL,                   -- PLAC.MAP.LATI (optional)
  long_raw TEXT NULL,                   -- PLAC.MAP.LONG (optional)

  -- stable dedupe helper (same PLAC+FORM in same run)
  place_hash TEXT GENERATED ALWAYS AS (
    md5(coalesce(plac_raw,'') || '|' || coalesce(form_raw,''))
  ) STORED,

  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Dedupe identical PLAC+FORM within a run
CREATE UNIQUE INDEX IF NOT EXISTS ux_place_occurrence_run_hash
  ON ged.place_occurrence(run_id, place_hash);

-- Speed up “show me places in this run”
CREATE INDEX IF NOT EXISTS ix_place_occurrence_run_id
  ON ged.place_occurrence(run_id);

-- Trigram search index for later fuzzy matching against plac_raw
CREATE INDEX IF NOT EXISTS ix_place_occurrence_plac_raw_trgm
  ON ged.place_occurrence USING gin (plac_raw gin_trgm_ops);

-- 4) Optional: Parsing results (future phase)
CREATE TABLE IF NOT EXISTS ged.place_parse (
  place_occurrence_id BIGINT PRIMARY KEY
    REFERENCES ged.place_occurrence(place_occurrence_id) ON DELETE CASCADE,
  tokens JSONB NULL,
  normalized TEXT NULL,
  parse_method TEXT NOT NULL DEFAULT 'unparsed',
  quality_flags JSONB NULL,
  parsed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 5) Candidate matches (future phase)
CREATE TABLE IF NOT EXISTS ged.place_match_candidate (
  place_occurrence_id BIGINT NOT NULL
    REFERENCES ged.place_occurrence(place_occurrence_id) ON DELETE CASCADE,
  geonameid INTEGER NOT NULL
    REFERENCES geonames.allcountries(geonameid),
  score NUMERIC(6,3) NOT NULL,
  reasons JSONB NULL,
  PRIMARY KEY (place_occurrence_id, geonameid)
);

-- 6) Final resolution (future phase)
CREATE TABLE IF NOT EXISTS ged.place_resolution (
  place_occurrence_id BIGINT PRIMARY KEY
    REFERENCES ged.place_occurrence(place_occurrence_id) ON DELETE CASCADE,
  geonameid_selected INTEGER NULL
    REFERENCES geonames.allcountries(geonameid),
  resolution_method TEXT NOT NULL DEFAULT 'unresolved', -- manual/auto/unresolved
  confidence NUMERIC(4,3) NULL,
  notes TEXT NULL,
  resolved_at TIMESTAMPTZ NULL
);

CREATE INDEX IF NOT EXISTS ix_candidate_score
  ON ged.place_match_candidate(place_occurrence_id, score DESC);

CREATE INDEX IF NOT EXISTS ix_resolution_geonameid
  ON ged.place_resolution(geonameid_selected);

-- 7) Helpful indexes on GeoNames tables (safe if already exist)
CREATE INDEX IF NOT EXISTS ix_hierarchy_parentid ON geonames.hierarchy(parentid);
CREATE INDEX IF NOT EXISTS ix_hierarchy_childid  ON geonames.hierarchy(childid);

CREATE INDEX IF NOT EXISTS ix_allcountries_country_admin
  ON geonames.allcountries(country_code, admin1_code, admin2_code);

CREATE INDEX IF NOT EXISTS ix_allcountries_name_trgm
  ON geonames.allcountries USING gin (name gin_trgm_ops);

CREATE INDEX IF NOT EXISTS ix_allcountries_asciiname_trgm
  ON geonames.allcountries USING gin (asciiname gin_trgm_ops);

CREATE INDEX IF NOT EXISTS ix_alternatenames_name_trgm
  ON geonames.alternatenames USING gin (alternate_name gin_trgm_ops);

CREATE INDEX IF NOT EXISTS ix_alternatenames_geonameid
  ON geonames.alternatenames(geonameid);
