\set ON_ERROR_STOP on

-- expects: -v run_id='...'
INSERT INTO ged.place_candidates (run_id, place_hash, plac_raw, geonameid, score, reasons)
SELECT
  d.run_id,
  d.place_hash,
  d.plac_raw,
  c.geonameid,
  c.rank_score::numeric(6,3) AS score,
  jsonb_build_object('method','first_token_us_pref') AS reasons
FROM ged.mv_distinct_places d
JOIN LATERAL (
  SELECT geonameid, rank_score
  FROM ged.geonames_candidates_first_token_us_pref(d.plac_raw, 10)
) c ON true
WHERE d.run_id = :run_id
ON CONFLICT DO NOTHING;
