# Neo4j Graph Projection

## Nodes
- Person
- Family
- Event
- Place
- Source

## Relationships
- CHILD_OF
- SPOUSE_IN
- HAS_EVENT
- ASSOCIATED_WITH

## Projection Rules
- Graph is derived from PostgreSQL.
- Nodes carry stable_id and ingestion watermark.
- Graph may be rebuilt without loss of truth.
