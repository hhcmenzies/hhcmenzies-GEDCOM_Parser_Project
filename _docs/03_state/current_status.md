# Current Project Status

*Last updated: 2026-02-09*

## What works

* Package installs editable: pip install -e .
* CLI entrypoint: gedcom
* CLI commands: doctor,
  ersion, stats, export
* CLI documentation generators:

  * scripts/docs/generate\_cli\_docs.ps1
  * scripts/docs/generate\_cli\_reference.ps1
  * scripts/docs/generate\_all.ps1

* Repo line endings governed by .gitattributes (LF normalized)

## What does not work / pain points

* Pipeline stages beyond parse/export are not implemented as CLI stages yet (ingest/normalize/enrich/validate/project)
* Config precedence and runtime provenance/run\_id manifest not yet formalized in code + docs

## Today’s goal

* Produce a complete AI handoff bundle (docs + scripts + configs + inventories + design PDF)
* Start next milestone plan: staged pipeline scaffolding + run\_id/provenance manifest

## Next actions (ordered)

1. Run pwsh -NoProfile -File scripts/docs/generate\_all.ps1 and confirm clean git diff for generated docs
2. Write today’s \_docs/06\_handoff/2026-02-09.md
3. Build handoff zip to H:\\ and attach it to the new chat

## Blockers

* 

## Notes

* \_docs/ is authoritative; /docs is deprecated and should be migrated intentionally.
