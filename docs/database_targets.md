# Database Targets and Examples

This document outlines how the project connects to alternative databases and what adjustments are needed for PostgreSQL and Neo4j support.

## PostgreSQL via SQLAlchemy

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

engine = create_engine("postgresql+psycopg2://user:password@localhost:5432/gedcom")

with Session(engine) as session:
    session.execute("SELECT 1")
```

### Adapting `json_to_sql.py`

- Replace `sqlite3` with SQLAlchemy and load the connection string from `config.yaml`.
- Use `create_engine()` to connect: `engine = create_engine(POSTGRES_URI)`.
- Execute the existing `gedcom_schema.sql` script against PostgreSQL before inserting records.
- Adjust placeholder syntax to `%s` if using raw `cursor.execute()` calls.

## Neo4j via Official Driver

```python
from neo4j import GraphDatabase

uri = "bolt://localhost:7687"
driver = GraphDatabase.driver(uri, auth=("neo4j", "password"))

with driver.session() as session:
    session.run("RETURN 1")
```

### Neo4j Data Model

- `Person` nodes for individuals with properties such as `gid`, `name`, and `birth_date`.
- `Family` nodes representing GEDCOM family groups.
- Relationships like `PARENT_OF`, `SPOUSE_OF`, and `MEMBER_OF` linking people and families.
- Planned script: `gedcom_to_neo4j.py` will create nodes and relationships from the parsed JSON.

---
