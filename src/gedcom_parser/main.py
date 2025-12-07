"""
Main entry for GEDCOM Parser Project.
"""

from __future__ import annotations
import argparse
from pathlib import Path
from gedcom_parser.config import get_config
from gedcom_parser.logging import get_logger
from gedcom_parser.parser_core import GEDCOMParser
from gedcom_parser.exporter import export_registry_to_json

log = get_logger(__name__)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="GEDCOM Parser Project – Phase 1 Backbone"
    )
    parser.add_argument(
        "-i", "--input",
        required=True,
        help="Path to GEDCOM input file"
    )
    parser.add_argument(
        "-o", "--output",
        default="outputs/export.json",
        help="Final output JSON path"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug output"
    )
    return parser


def run(input_path: str, output_path: str, debug_flag: bool):
    cfg = get_config()
    cfg.debug = bool(debug_flag)

    log.info(f"Loading GEDCOM: {input_path}")

    parser = GEDCOMParser(config=cfg)

    registry = parser.run(input_path)

    # EXPORT: now supports (registry, out_path)
    export_registry_to_json(registry, output_path)

    log.info(f"Main pipeline complete. Output: {output_path}")


def main():
    ap = build_arg_parser()
    args = ap.parse_args()

    try:
        run(
            input_path=args.input,
            output_path=args.output,
            debug_flag=args.debug
        )
    except Exception as exc:
        log.exception(f"Unhandled exception in main: {exc}")
        raise


if __name__ == "__main__":
    main()
