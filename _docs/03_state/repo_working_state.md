# Repo Working State

_Last updated: 2026-02-08_

## Git Identity and Remote
- Remote: `origin` (GitHub)
- Branching model: `main` as default

## Line Endings / Attributes
- `.gitattributes` present
- Expected: text normalized to LF, binary-like assets marked `-text`

## Local Environment (Developer Machine)
- OS: Windows 11
- Shell: PowerShell (PyCharm terminal)
- Python: venv/conda used (document exact env name below)

## Python Environment (Fill In)
- Interpreter path:
- Virtual env name:
- `pip freeze` captured? (yes/no)
- Key tooling installed:
  - pytest
  - black/ruff (if used)
  - psycopg / sqlalchemy (if used)

## Database Connections (Fill In)
- PostgreSQL DB name: `gedcom`
- Host/Port/User:
- PyCharm DataGrip connection: configured (yes/no)
- Neo4j: configured (yes/no)

## Quick Commands (Reference)
### Git
- `git status`
- `git log -10 --oneline --decorate`
- `git diff`

### PostgreSQL
- `psql -d gedcom`
- `psql -d gedcom -f db/setup_places.sql`

## Working Agreements
- Authoritative docs live in `_docs/`
- Legacy `/docs/` is ignored
- Track only intentional generated exports under `_docs/_exports/`
