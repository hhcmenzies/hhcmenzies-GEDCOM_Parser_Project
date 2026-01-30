#!/usr/bin/env python3
import argparse
import os
from src.gedcom_parser.main_pipeline import run_pipeline

def main():
    parser = argparse.ArgumentParser(description="Run GEDCOM Parsing and Enrichment Pipeline")
    parser.add_argument("--gedcom", required=True, help="Path to GEDCOM file")
    parser.add_argument("--outdir", default="outputs/parsed", help="Directory to write output JSON")
    parser.add_argument("--config", default=None, help="Optional JSON config override file")
    args = parser.parse_args()

    run_pipeline(
        gedcom_path=args.gedcom,
        outdir=args.outdir,
        config_override=args.config
    )

if __name__ == "__main__":
    main()
