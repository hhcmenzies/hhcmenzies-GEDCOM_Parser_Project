# Data Model

## Raw Layer
- ingestion_run
- ingested_file
- gedcom_raw_node
- gedcom_raw_line (optional)
- run_issue

## Canonical Layer
- person
- family
- event
- place
- source
- citation
- media

## Fact Layer
- entity_fact (captures standardized but unmapped tags)

## Enrichment Layer
- enrichment_result (stores derived interpretations with provenance)

## DNA
- dna_kit
- dna_match
- dna_segment
- kit_person_link
