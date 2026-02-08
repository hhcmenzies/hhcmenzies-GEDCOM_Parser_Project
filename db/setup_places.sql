-- db/setup_places.sql

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE SCHEMA IF NOT EXISTS ged;

-- (short) keep just the function for now so you dont keep re-running huge DDL
CREATE OR REPLACE FUNCTION ged.geonames_candidates_first_token(
  p_query TEXT,
  p_limit INT DEFAULT 25
)
RETURNS TABLE (
  geonameid INT,
  name TEXT,
  asciiname TEXT,
  country_code TEXT,
  admin1_code TEXT,
  admin2_code TEXT,
  feature_class TEXT,
  feature_code TEXT,
  population BIGINT,
  score NUMERIC
)
LANGUAGE sql
STABLE
AS $$
  WITH q AS (SELECT trim(split_part(p_query, ',', 1)) AS token)
  SELECT
    a.geonameid,
    a.name,
    a.asciiname,
    a.country_code,
    a.admin1_code,
    a.admin2_code,
    a.feature_class,
    a.feature_code,
    a.population,
    GREATEST(similarity(a.name, q.token), similarity(a.asciiname, q.token))::numeric(6,3) AS score
  FROM geonames.allcountries a
  CROSS JOIN q
  WHERE a.name % q.token OR a.asciiname % q.token
  ORDER BY score DESC, population DESC NULLS LAST
  LIMIT p_limit;
$$;
