"""
File Locator

Resolves absolute, validated paths to input GEDCOM/JSON files.
"""

import os
from rich import print as rprint

from gedcom_parser.logging import get_logger

log = get_logger(__name__)


def resolve_input_path(path: str | None) -> str | None:
    """
    Convert a user-provided path into an absolute validated file path.

    Returns:
        Absolute path string, or None if no input path was provided.
    """
    if path is None:
        log.debug("No input path provided to resolve_input_path().")
        return None

    abs_path = os.path.abspath(path)
    log.debug(f"Resolving input file: {abs_path}")

    if not os.path.exists(abs_path):
        log.error(f"Input file does not exist: {abs_path}")
        raise FileNotFoundError(f"Input file not found: {abs_path}")

    if not os.path.isfile(abs_path):
        log.error(f"Input path is not a file: {abs_path}")
        raise ValueError(f"Input path is not a file: {abs_path}")

    log.debug(f"Validated input file: {abs_path}")
    return abs_path
