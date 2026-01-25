# MA Notables upgrade v2.4

What this pack does:
- Adds role-driven collections (military, legislators, judges) and a few targeted colonial-era add-ons (clergy, writers/poets, Mayflower Compact signatories).
- Fixes common Wikipedia-title failures by preferring list pages for judges.
- Tightens `eighteenth_century_ma` to end at 1799 to match the project target window.

How to install into `~/GEDCOM_Parser_Project`:
```bash
cd ~/GEDCOM_Parser_Project
cp -f ma_notables_upgrade_v2_4/* .
chmod +x preflight_ma_notables.py run_ma_notables.sh verify_ma_notables.sh
python -m pip install -r requirements-ma-notables.txt
```

How to run (with live Wikipedia checks enabled):
```bash
./run_ma_notables.sh collections.json "MA-Notables/1.0 (contact: david.menzies@gmail.com)" 1
./verify_ma_notables.sh out/runs/latest
```

Notes:
- Wikipedia checks may warn `NOT OK (HTTP 200)`. This usually means the API request succeeded, but the *title does not exist* (missing page) or is a redirect that resolves to a non-category/non-article page.
- If you see 0-line outputs for a collection, start by checking titles with the preflight (CHECK_WIKIPEDIA=1).
