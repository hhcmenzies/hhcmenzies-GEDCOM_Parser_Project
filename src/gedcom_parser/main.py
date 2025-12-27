"""
Main entry for GEDCOM Parser Project.

This module is intentionally thin:
- argument parsing
- configuration setup
- pipeline orchestration

No parsing or business logic lives here.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from gedcom_parser.config import get_config
from gedcom_parser.logger import get_logger

from gedcom_parser.core.context import ParseContext
from gedcom_parser.core.pipeline import Pipeline

log = get_logger("main")


# ---------------------------------------------------------
# CLI Argument Parsing
# ---------------------------------------------------------
def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="GEDCOM Parser Project – Phase 1 Backbone"
    )
    parser.add_argument(
        "-i",
        "--input",
        required=True,
        help="Path to GEDCOM input file",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="outputs/export.json",
        help="Final output JSON path",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug output",
    )
    return parser


# ---------------------------------------------------------
# Pipeline Runner
# ---------------------------------------------------------
def run(input_path: str, output_path: str, debug_flag: bool) -> None:
    """
    Prepare context and execute the parsing pipeline.
    """

    cfg = get_config()
    cfg.debug = bool(debug_flag)

    log.info(f"Loading GEDCOM: {input_path}")

    ctx = ParseContext(
        config=cfg,
        logger=log,
        input_path=input_path,
        output_path=output_path,
        debug=cfg.debug,
    )

    pipeline = Pipeline(ctx)
    pipeline.run()

    log.info(f"Main pipeline complete. Output: {output_path}")


# ---------------------------------------------------------
# Program Entry Point
# ---------------------------------------------------------
def main() -> None:
    ap = build_arg_parser()
    args = ap.parse_args()

    try:
        run(
            input_path=args.input,
            output_path=args.output,
            debug_flag=args.debug,
        )
    except Exception as exc:
        log.exception(f"Unhandled exception in main: {exc}")
        raise


if __name__ == "__main__":
    main()
