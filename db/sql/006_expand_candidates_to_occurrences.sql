\set ON_ERROR_STOP on

-- expects: -v run_id='...'
INSERT INTO ged.place_match_candidate (place_occurrence_id, geonameid, score, reasons)
SELECT
  po.place_occurrence_id,
  pc.geonameid,
  pc.score,
  pc.reasons
FROM ged.place_occurrence po
JOIN ged.place_candidates pc
  ON pc.run_id = po.run_id
 AND pc.place_hash = po.place_hash
WHERE po.run_id = :run_id
ON CONFLICT DO NOTHING;
