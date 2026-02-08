CREATE OR REPLACE FUNCTION ged.geonames_candidates_first_token_us_pref(
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
  score NUMERIC,
  rank_score NUMERIC
)
LANGUAGE sql
STABLE
AS $$
  WITH q AS (
    SELECT
      trim(split_part(p_query, ',', 1)) AS token,
      upper(trim(split_part(p_query, ',', 2))) AS hint2,
      upper(trim(split_part(p_query, ',', 3))) AS hint3
  )
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
    GREATEST(similarity(a.name, q.token), similarity(a.asciiname, q.token))::numeric(6,3) AS score,
    (
      GREATEST(similarity(a.name, q.token), similarity(a.asciiname, q.token))
      + CASE
          WHEN q.hint3 IN ('USA','US') AND a.country_code='US' THEN 0.30
          WHEN q.hint3<>'' AND a.country_code=q.hint3 THEN 0.20
          ELSE 0
        END
      + CASE
          WHEN q.hint2 IN ('MA','MASSACHUSETTS') AND a.country_code='US' AND a.admin1_code='MA' THEN 0.30
          ELSE 0
        END
    )::numeric(6,3) AS rank_score
  FROM geonames.allcountries a
  CROSS JOIN q
  WHERE a.name % q.token OR a.asciiname % q.token
  ORDER BY rank_score DESC, population DESC NULLS LAST
  LIMIT p_limit;
$$;
