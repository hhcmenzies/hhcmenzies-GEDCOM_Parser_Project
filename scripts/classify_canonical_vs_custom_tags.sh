#!/usr/bin/env bash
# Stage 2: Canonical Tag Classification
# Description: Identifies non-standard (custom) tags by comparing enriched records against a canonical tag list.
# Inputs: 
#   1) outputs/structured/enriched/enriched_records.import2.json 
#   2) datasets/gedcom/canonical/canonical_tag_dictionary_gedcom551.patched.json 
# Output: inventory/latest/custom_tags_report.import2.json
# (Ensure the 'inventory/latest' directory exists for output)
mkdir -p inventory/latest

echo "Running Canonical Tag Classification..."
python scripts/analyze_tag_standard_vs_custom.py \
    -i outputs/structured/enriched/enriched_records.import2.json \
    -d datasets/gedcom/canonical/canonical_tag_dictionary_gedcom551.patched.json \
    -o inventory/latest/custom_tags_report.import2.json
