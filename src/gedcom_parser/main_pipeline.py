import os
import json
from pathlib import Path
from src.gedcom_parser.config import DEFAULTS
from scripts.capture_gedcom_raw import main as capture_main

def run_pipeline(gedcom_path, outdir, config_override=None):
    # Load config
    config = DEFAULTS.copy()
    if config_override:
        with open(config_override, "r", encoding="utf-8") as f:
            user_config = json.load(f)
            config.update(user_config)

    gedcom_path = Path(gedcom_path)
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    print(f"Running pipeline on: {gedcom_path}")
    print(f"Output directory: {outdir}")

    # === Step 1: Raw Capture ===
    os.system(f"python3 scripts/capture_gedcom_raw.py "
              f"--ged '{gedcom_path}' "
              f"--canonical-tags '{config['canonical_tag_dict']}' "
              f"--out-dir '{outdir}' "
              f"--treat-underscore-as-known")

    print("✅ Raw GEDCOM capture complete.")

    # === Step 2: Grammar Audit (optional extension later)
    # === Step 3: Merge vendor extensions (optional)
    # === Step 4: Build context index (optional)
    # === Step 5: Enrichment (optional)

    print("🟢 Pipeline completed (Phase 3 baseline).")

