# Configuration Contract (Precedence and Shape)

_Last updated: 2026-02-09_

This document defines how configuration is located, loaded, merged, and fingerprinted.

## Precedence (highest to lowest)
1) Explicit CLI flag: --config <path>
2) Environment variable: GEDCOM_CONFIG (optional future)
3) Default project config: config/processing_config.yml

## Requirements
- Config must be loadable as YAML.
- The effective config used for a run must be fingerprintable (stable hash of normalized structure).
- Missing config must fail clearly (no silent defaults beyond the known fallback path).

## Notes
- Update this file if `src/gedcom_parser/config.py` changes behavior.
