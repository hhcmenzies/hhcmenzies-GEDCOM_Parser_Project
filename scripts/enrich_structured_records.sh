#!/usr/bin/env bash
# Stage 1: Structured Record Enrichment
# Description: Enriches the structured GEDCOM records with additional computed fields and context.
# Input:  outputs/structured/structured_records.import2.json 
# Output: outputs/structured/enriched/enriched_records.import2.json 
# (Ensure the 'outputs/structured/enriched' directory exists)
mkdir -p outputs/structured/enriched

echo "Running Structured Record Enrichment..."
python scripts/enrich_structured_records.py \
    -i outputs/structured/structured_records.import2.json \
    -o outputs/structured/enriched/enriched_records.import2.json
