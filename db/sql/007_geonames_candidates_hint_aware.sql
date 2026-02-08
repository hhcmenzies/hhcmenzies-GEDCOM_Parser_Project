CREATE OR REPLACE FUNCTION ged.geonames_candidates_hint_aware(
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
  base_score NUMERIC,
  rank_score NUMERIC
)
LANGUAGE sql
STABLE
AS $$
WITH parts AS (
  SELECT
    trim(split_part(p_query, ',', 1)) AS token,
    upper(trim(split_part(p_query, ',', 2))) AS h2,
    upper(trim(split_part(p_query, ',', 3))) AS h3,
    upper(trim(split_part(p_query, ',', 4))) AS h4,
    upper(trim(split_part(p_query, ',', 5))) AS h5,
    upper(trim(split_part(p_query, ',', 6))) AS h6
),
hints AS (
  SELECT
    token,
    NULLIF(h2,'') AS h2,
    NULLIF(h3,'') AS h3,
    NULLIF(h4,'') AS h4,
    NULLIF(h5,'') AS h5,
    NULLIF(h6,'') AS h6,
    COALESCE(NULLIF(h6,''), NULLIF(h5,''), NULLIF(h4,''), NULLIF(h3,''), NULLIF(h2,'')) AS country_hint
  FROM parts
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
  GREATEST(similarity(a.name, h.token), similarity(a.asciiname, h.token))::numeric(6,3) AS base_score,
  (
    GREATEST(similarity(a.name, h.token), similarity(a.asciiname, h.token))
    + CASE
        WHEN h.country_hint IN ('USA','US','UNITED STATES','UNITED STATES OF AMERICA','U.S.','U.S.A.')
             AND a.country_code='US' THEN 0.45
        WHEN h.country_hint IN ('ENGLAND','SCOTLAND','WALES','NORTHERN IRELAND','UNITED KINGDOM','UK','GREAT BRITAIN','BRITAIN')
             AND a.country_code='GB' THEN 0.45
        WHEN h.country_hint IN ('CANADA','CA') AND a.country_code='CA' THEN 0.45
        WHEN h.country_hint IN ('AUSTRALIA','AU') AND a.country_code='AU' THEN 0.45
        WHEN h.country_hint IS NOT NULL AND length(h.country_hint)=2 AND a.country_code=h.country_hint THEN 0.35
        ELSE 0
      END
    + CASE
        WHEN a.country_code='US'
         AND (h.h2 ~ '^[A-Z]{2}$' OR h.h3 ~ '^[A-Z]{2}$' OR h.h4 ~ '^[A-Z]{2}$')
         AND a.admin1_code IN (h.h2, h.h3, h.h4)
        THEN 0.35
        ELSE 0
      END
    + CASE
        WHEN a.population IS NOT NULL AND a.population > 0
        THEN LEAST(0.08, ln(a.population+1)/200.0)
        ELSE 0
      END
  )::numeric(6,3) AS rank_score
FROM geonames.allcountries a
CROSS JOIN hints h
WHERE (a.name % h.token OR a.asciiname % h.token)
  AND a.feature_class IN ('P','A')
ORDER BY rank_score DESC, population DESC NULLS LAST
LIMIT p_limit;
$$;
