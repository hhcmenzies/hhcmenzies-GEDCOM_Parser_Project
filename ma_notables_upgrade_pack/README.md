# MA Notables Pipeline – Upgraded Files

## What’s included
- `ma_notables_pipeline.py` – upgraded pipeline:
  - supports v2 config (`project.target_window`, `collections[].sources[]`)
  - human-only filter using Wikidata `P31 == Q5`
  - adds date precision fields
  - produces quarantine files and a QA report
- `collections.schema.json` – JSON Schema for config validation
- `collections.upgraded.json` – your config with `schema_version` added
- `requirements.txt` – minimal deps

## Quick start
```bash
python -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt

python ma_notables_pipeline.py --config collections.upgraded.json --outdir out --user-agent "YourProject/1.0 (email@example.com)"
```

## Outputs
- `out/master_ma_1600_1799.jsonl`
- `out/collections/*.jsonl`
- `out/manifest.json`
- `out/qa_report.json`
- `out/rejected_no_qid.jsonl`
- `out/rejected_nonhuman.jsonl`
- `out/rejected_outside_window.jsonl`
