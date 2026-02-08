CREATE OR REPLACE FUNCTION ged.geonames_candidates_hint_aware_v2(
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
WITH norm AS (
  SELECT
    -- normalize punctuation, collapse whitespace
    regexp_replace(regexp_replace(coalesce(p_query,''), '[\(\)\[\]\{\}]', ' ', 'g'), '\s+', ' ', 'g') AS q
),
parts AS (
  SELECT
    q,
    -- split on comma OR " - " OR " / " as a fallback, but keep whole string too
    regexp_split_to_array(q, '\s*,\s*') AS comma_parts,
    regexp_split_to_array(q, '\s+') AS words
  FROM norm
),
hints AS (
  SELECT
    q,

    -- token = first comma part if present, else first 3 words joined
    CASE
      WHEN array_length(comma_parts,1) >= 1 AND length(trim(comma_parts[1])) > 0
        THEN trim(comma_parts[1])
      ELSE trim(
        coalesce(words[1],'') || ' ' || coalesce(words[2],'') || ' ' || coalesce(words[3],'')
      )
    END AS token,

    -- raw country-ish hint: look for explicit keywords anywhere
    CASE
      WHEN q ~* '\b(usa|u\.s\.a\.|u\.s\.|united states|united states of america)\b' THEN 'US'
      WHEN q ~* '\b(canada)\b' THEN 'CA'
      WHEN q ~* '\b(australia)\b' THEN 'AU'
      WHEN q ~* '\b(united kingdom|uk|great britain|britain)\b' THEN 'GB'
      WHEN q ~* '\b(england|scotland|wales|northern ireland)\b' THEN 'GB'
      ELSE NULL
    END AS country_norm,

    -- US state hint: find a standalone 2-letter token that is a plausible state code
    -- (This is a heuristic; it is still safer than using split_part)
    (
      SELECT upper(w)
      FROM unnest(words) w
      WHERE w ~* '^[A-Za-z]{2}$'
        AND upper(w) IN (
          'AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IL','IN','IA','KS','KY','LA','ME','MD',
          'MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI','SC',
          'SD','TN','TX','UT','VT','VA','WA','WV','WI','WY','DC'
        )
      LIMIT 1
    ) AS us_state_hint
  FROM parts
),
filtered_token AS (
  SELECT
    *,
    -- stopword + too-short protection
    CASE
      WHEN token IS NULL THEN NULL
      WHEN length(trim(token)) < 3 THEN NULL
      WHEN upper(trim(token)) IN ('OF','THE','AND','OR','QUALITY','UNKNOWN','?') THEN NULL
      ELSE trim(token)
    END AS token_ok
  FROM hints
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

  -- base similarity (0..1-ish)
  GREATEST(similarity(a.name, f.token_ok), similarity(a.asciiname, f.token_ok))::numeric(6,3) AS base_score,

  -- bounded rank_score: base + small boosts, then clamp to [0,1]
  LEAST(
    1.000,
    GREATEST(
      0.000,
      (
        GREATEST(similarity(a.name, f.token_ok), similarity(a.asciiname, f.token_ok))
        + CASE
            -- HARD country preference via WHERE below; this is only a tiny nudge for ties
            WHEN f.country_norm IS NOT NULL AND a.country_code = f.country_norm THEN 0.05
            ELSE 0
          END
        + CASE
            -- US state hint helps only inside US
            WHEN f.us_state_hint IS NOT NULL AND a.country_code = 'US' AND a.admin1_code = f.us_state_hint THEN 0.10
            ELSE 0
          END
        + CASE
            -- population nudge
            WHEN a.population IS NOT NULL AND a.population > 0 THEN LEAST(0.05, ln(a.population+1)/300.0)
            ELSE 0
          END
      )
    )
  )::numeric(6,3) AS rank_score
FROM filtered_token f
JOIN geonames.allcountries a ON true
WHERE f.token_ok IS NOT NULL
  AND (a.name % f.token_ok OR a.asciiname % f.token_ok)
  AND a.feature_class IN ('P','A')

  -- HARD country filter if we detected one.
  -- Include US territories when the query says "USA".
  AND (
    f.country_norm IS NULL
    OR (
      f.country_norm = 'US'
      AND a.country_code IN ('US','PR','GU','VI','MP','AS','UM')
    )
    OR (
      f.country_norm <> 'US'
      AND a.country_code = f.country_norm
    )
  )
ORDER BY rank_score DESC, population DESC NULLS LAST
LIMIT p_limit;
$$;
