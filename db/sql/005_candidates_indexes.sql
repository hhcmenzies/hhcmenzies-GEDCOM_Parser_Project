BEGIN;

-- helps "have we already generated candidates for this place_occurrence_id?"
CREATE INDEX IF NOT EXISTS ix_pmc_place_occurrence_id
  ON ged.place_match_candidate(place_occurrence_id);

-- helps ON CONFLICT and ordering (if not already present)
CREATE INDEX IF NOT EXISTS ix_pmc_place_occurrence_geonameid
  ON ged.place_match_candidate(place_occurrence_id, geonameid);

COMMIT;
