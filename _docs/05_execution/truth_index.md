# Truth Index

This file defines what is considered authoritative and where it lives.

## Documentation (Authoritative)
- H:\docs\AI_CONTRACT.md
- H:\docs\DAILY_START.md
- H:\docs\CHAT_BRIEFING.md
- H:\docs\00_contract\*.md
- H:\docs\02_architecture\*.md
- H:\docs\03_state\current_status.md
- H:\docs\03_state\active_work.md
- H:\docs\06_handoff\YYYY-MM-DD.md

## Audit Inputs (Reference Only)
- H:\_audit\<timestamp>\* (used to generate docs, not itself “truth”)

## Code (Authoritative Implementation)
- H:\Projects\GEDCOM_Parser_Project\ (detected repo)
  - source truth for actual running code once verified

## Data (Authoritative Raw Sources)
- GEDCOM and DNA input datasets: to be explicitly listed once identified from repo + inventory

## Graph Output (Derived)
- Neo4j database is derived/projection and must be rebuildable from PostgreSQL.
