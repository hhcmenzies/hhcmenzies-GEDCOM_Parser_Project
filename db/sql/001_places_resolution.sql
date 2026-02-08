-- ===== Extensions =====
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;

-- Optional: PostGIS if you want geom indexing / distance queries later.
-- CREATE EXTENSION IF NOT EXISTS postgis;

-- ===== Enums =====
DO $$ BEGIN
  CREATE TYPE import_status AS ENUM ('CREATED', 'RUNNING', 'COMPLETED', 'FAILED');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE resolution_type AS ENUM ('SELECTED', 'KEEP_VERBATIM', 'IGNORED', 'SPLIT_DETAIL_ONLY');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE apply_scope AS ENUM ('THIS_ONLY', 'ALL_SAME_RAW', 'ALL_SAME_NORMALIZED', 'RULE');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE match_type AS ENUM ('RAW_EQUALS', 'RAW_REGEX', 'NORMALIZED_EQUALS', 'PARSED_MATCH', 'IMPORT_ONLY');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE action_type AS ENUM ('SELECT_CANDIDATE', 'KEEP_VERBATIM', 'SPLIT_DETAIL');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ===== Core Tables =====

-- Track imports (a GEDCOM load session)
CREATE TABLE IF NOT EXISTS import_run (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_name     text NOT NULL,                       -- filename or user label
  created_at      timestamptz NOT NULL DEFAULT now(),
  started_at      timestamptz NULL,
  finished_at     timestamptz NULL,
  status          import_status NOT NULL DEFAULT 'CREATED',
  settings_json   jsonb NOT NULL DEFAULT '{}'::jsonb,
  error_text      text NULL
);

-- Canonical place string entity (deduped)
CREATE TABLE IF NOT EXISTS place_string (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),

  -- keep original GEDCOM PLAC verbatim
  raw_text           text NOT NULL,

  -- normalized form (what your system proposes/uses)
  normalized_text    text NULL,

  -- “detail” extracted from raw (cemetery/church/address) – optional
  detail_text        text NULL,

  -- parsed components (locality/admin/country/etc.)
  parsed_json        jsonb NOT NULL DEFAULT '{}'::jsonb,

  -- optional language/culture guesses, if you want
  language_guess     text NULL,
  culture_guess      text NULL,

  -- hashes for dedupe (store as bytea or text; text is fine)
  hash_raw           text NOT NULL,
  hash_normalized    text NULL,

  created_at         timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT place_string_hash_raw_unique UNIQUE (hash_raw)
);

-- Where that place appears (provenance + context)
CREATE TABLE IF NOT EXISTS place_usage (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  place_string_id uuid NOT NULL REFERENCES place_string(id) ON DELETE CASCADE,
  import_run_id   uuid NOT NULL REFERENCES import_run(id) ON DELETE CASCADE,

  entity_type     text NOT NULL,            -- "INDI", "FAM", "EVENT", etc. (or your internal types)
  entity_id       uuid NOT NULL,            -- UUID in your canonical model
  event_type      text NULL,                -- BIRT/DEAT/MARR/etc
  gedcom_path     text NULL,                -- e.g., "INDI.BIRT.PLAC"
  xref_id         text NULL,                -- e.g., "@I123@"
  line_no         integer NULL,

  -- for historical plausibility (even year helps)
  date_context    text NULL,                -- store normalized date string or year, flexible

  created_at      timestamptz NOT NULL DEFAULT now()
);

-- Candidate matches from gazetteers/datasets/resolvers
CREATE TABLE IF NOT EXISTS place_candidate (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  place_string_id   uuid NOT NULL REFERENCES place_string(id) ON DELETE CASCADE,

  source            text NOT NULL,          -- "your_dataset", "geonames", "tiger", etc.
  external_id       text NOT NULL,          -- key in that dataset

  display_name      text NOT NULL,          -- user-facing candidate label
  admin_path_json   jsonb NOT NULL DEFAULT '{}'::jsonb,

  lat               double precision NULL,
  lon               double precision NULL,
  -- geom             geometry(Point, 4326) NULL, -- if PostGIS

  feature_class     text NULL,
  feature_code      text NULL,

  valid_from        date NULL,
  valid_to          date NULL,

  score_total       double precision NOT NULL DEFAULT 0,
  score_breakdown_json jsonb NOT NULL DEFAULT '{}'::jsonb,
  evidence_json     jsonb NOT NULL DEFAULT '{}'::jsonb,

  created_at        timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT place_candidate_dedupe UNIQUE (place_string_id, source, external_id)
);

-- User/system decisions (audit trail)
CREATE TABLE IF NOT EXISTS place_resolution (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  place_string_id     uuid NOT NULL REFERENCES place_string(id) ON DELETE CASCADE,

  selected_candidate_id uuid NULL REFERENCES place_candidate(id) ON DELETE SET NULL,

  resolution_type     resolution_type NOT NULL,
  confidence          double precision NULL,      -- 0..1, or NULL for keep/ignore
  reason              text NULL,

  resolved_by         text NOT NULL DEFAULT 'system', -- username/service name
  resolved_at         timestamptz NOT NULL DEFAULT now(),

  applies_to_scope    apply_scope NOT NULL DEFAULT 'THIS_ONLY',
  rule_id             uuid NULL,  -- optional link to place_rule

  -- keep history; do not enforce single current row here
  -- if you want "current resolution", use a view (below)
  CONSTRAINT resolution_candidate_required
    CHECK (
      (resolution_type = 'SELECTED' AND selected_candidate_id IS NOT NULL)
      OR (resolution_type <> 'SELECTED')
    )
);

-- Rules that enable automatic/bulk resolution
CREATE TABLE IF NOT EXISTS place_rule (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name            text NOT NULL,
  enabled         boolean NOT NULL DEFAULT true,

  match_type      match_type NOT NULL,
  match_expr      text NOT NULL,       -- equals string, regex, JSON query, etc.
  import_only     boolean NOT NULL DEFAULT false, -- if rule applies only within import

  action_type     action_type NOT NULL,
  action_payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,

  priority        integer NOT NULL DEFAULT 100,

  created_at      timestamptz NOT NULL DEFAULT now()
);

-- ===== Helpful Views =====

-- Current resolution per place_string (latest by resolved_at)
CREATE OR REPLACE VIEW v_place_resolution_current AS
SELECT pr.*
FROM place_resolution pr
JOIN (
  SELECT place_string_id, max(resolved_at) AS max_resolved_at
  FROM place_resolution
  GROUP BY place_string_id
) latest
ON latest.place_string_id = pr.place_string_id
AND latest.max_resolved_at = pr.resolved_at;

-- ===== Indexes =====

CREATE INDEX IF NOT EXISTS idx_place_usage_place ON place_usage(place_string_id);
CREATE INDEX IF NOT EXISTS idx_place_usage_import ON place_usage(import_run_id);
CREATE INDEX IF NOT EXISTS idx_place_usage_entity ON place_usage(entity_type, entity_id);

CREATE INDEX IF NOT EXISTS idx_place_candidate_place ON place_candidate(place_string_id);
CREATE INDEX IF NOT EXISTS idx_place_candidate_score ON place_candidate(place_string_id, score_total DESC);

CREATE INDEX IF NOT EXISTS idx_place_resolution_place ON place_resolution(place_string_id, resolved_at DESC);

CREATE INDEX IF NOT EXISTS idx_place_rule_enabled_priority ON place_rule(enabled, priority);

-- Text search / filtering helpers
CREATE INDEX IF NOT EXISTS idx_place_string_hash_norm ON place_string(hash_normalized);
CREATE INDEX IF NOT EXISTS idx_place_string_norm_trgm ON place_string USING gin (normalized_text gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_place_string_raw_trgm  ON place_string USING gin (raw_text gin_trgm_ops);

-- For trigram indexes:
CREATE EXTENSION IF NOT EXISTS pg_trgm;
