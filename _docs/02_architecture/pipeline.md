# Processing Pipeline

## 1. Ingestion
- Identify input files
- Compute hashes
- Create ingestion run record

## 2. Parsing
- Parse GEDCOM into raw nodes
- Preserve levels, tags, values, and structure
- Record warnings and anomalies

## 3. Sterilization
- Normalize encoding (UTF-8)
- Trim whitespace
- Remove control characters

## 4. Standardization
- Apply tag registry rules
- Normalize dates, names, places, events
- Validate tag contexts and child relationships

## 5. Normalization
- Deduplicate entities
- Resolve references
- Produce canonical records

## 6. Enrichment
- Name variants
- Date interpretation
- Place parsing
- Optional spatial resolution

## 7. Load and Project
- Persist to PostgreSQL
- Project to Neo4j with watermarks
