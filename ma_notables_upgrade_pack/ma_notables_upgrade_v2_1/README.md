MA Notables Upgrade v2

This pack gives you the *correct* config + guardrails to avoid the recurring Shays title mistake,
plus utilities to run, verify, and convert legacy JSON datasets into the same JSONL person-shape.

Files
- collections.json                Canonical collections config (Shays's Rebellion fixed)
- collections.schema.json         Optional JSON schema (config validation)
- requirements-ma-notables.txt    Minimal dependency list
- preflight_ma_notables.py        Prints effective Shays sources + slugs before a run
- run_ma_notables.sh              Standard run wrapper (out/runs/<timestamp> + out/runs/latest)
- verify_ma_notables.sh           Verification wrapper (counts + quick JSON parse)
- convert_legacy_datasets.py      Converts legacy JSON arrays (Mayflower/Salem/Early MA) to JSONL

Install
  python -m pip install -r requirements-ma-notables.txt

Use (recommended)
  cp -f collections.json ~/GEDCOM_Parser_Project/collections.json
  cp -f preflight_ma_notables.py ~/GEDCOM_Parser_Project/preflight_ma_notables.py
  cp -f run_ma_notables.sh ~/GEDCOM_Parser_Project/run_ma_notables.sh
  cp -f verify_ma_notables.sh ~/GEDCOM_Parser_Project/verify_ma_notables.sh
  cp -f requirements-ma-notables.txt ~/GEDCOM_Parser_Project/requirements-ma-notables.txt

Run
  cd ~/GEDCOM_Parser_Project
  source venv/bin/activate
  python -m pip install -r requirements-ma-notables.txt
  ./run_ma_notables.sh collections.json "MA-Notables/1.0 (contact: david.menzies@gmail.com)"
  ./verify_ma_notables.sh out/runs/latest

Convert legacy datasets
  python convert_legacy_datasets.py --in /path/to/mayflower.json --dataset mayflower_passengers --label "Mayflower voyage" --out out/legacy_converted/mayflower.jsonl
  python convert_legacy_datasets.py --in /path/to/salem_witch_trials.json --dataset salem_witch_trials --label "Salem witch trials" --out out/legacy_converted/salem.jsonl
  python convert_legacy_datasets.py --in /path/to/early_massachusetts.json --dataset early_massachusetts --label "Early Massachusetts" --out out/legacy_converted/early_ma.jsonl


Preflight (with live Wikipedia checks)
python preflight_ma_notables.py --config collections.json --show

python preflight_ma_notables.py --config collections.json \
  --user-agent "MA-Notables/1.0 (contact: you@example.com)" \
  --check-wikipedia --sleep 0.1 --max-titles 500
