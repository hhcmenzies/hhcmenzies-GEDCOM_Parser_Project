# Architecture Overview

## High-Level Design
The system is organized as a pipeline that transforms raw genealogical data into
structured, standardized, and enriched representations.

## Core Layers
1. Raw Capture
2. Canonical Standardization
3. Enrichment
4. Projection (Graph)

Each layer is persisted independently and auditable.

## Control Plane
- Ingestion runs coordinate parsing, validation, and loading.
- Configuration governs parsing rules and enrichment behavior.

## Failure Strategy
- Parsing errors are recorded, not fatal.
- Validation errors may block downstream steps depending on severity.
- Enrichment failures do not invalidate canonical data.
