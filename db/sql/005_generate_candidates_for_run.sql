-- db/sql/005_generate_candidates_for_run.sql
-- Replace :run_id with your actual UUID when you run it.

INSERT INTO ged.place_match_candidate (place_occurrence_id, geonameid, score, reasons)
SELECT
  po.place_occurrence_id,
  c.geonameid,
  c.rank_score::numeric(6,3) AS score,
  jsonb_build_object('method','first_token_us_pref') AS reasons
FROM ged.place_occurrence po
JOIN LATERAL (
  SELECT geonameid, rank_score
  FROM ged.geonames_candidates_first_token_us_pref(po.plac_raw, 10)
) c ON true
WHERE po.run_id = :run_id
ON CONFLICT DO NOTHING;
