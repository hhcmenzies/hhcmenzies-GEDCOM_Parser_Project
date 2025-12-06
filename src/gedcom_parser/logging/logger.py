"""
Enhanced logging system for GEDCOM_Parser
Supports:
  - Unified root log (gedcom_parser.log)
  - Per-module logs (e.g., event_scoring.log, place_standardizer.log)
  - Rich console output
"""

import os
import logging
from rich.logging import RichHandler

LOG_DIR = "logs"
ROOT_LOG_FILE = os.path.join(LOG_DIR, "gedcom_parser.log")

def ensure_log_dir():
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR, exist_ok=True)


def get_logger(name: str = "GEDCOM_Parser") -> logging.Logger:
    """
    Creates a logger with:
      - Rich console handler
      - Root file handler
      - Per-module file handler (logs/<name>.log)
    """
    ensure_log_dir()

    logger = logging.getLogger(name)

    if logger.handlers:
        return logger  # Already configured

    logger.setLevel(logging.DEBUG)

    # ------------------------------------------------------------------
    # Console (pretty) handler
    # ------------------------------------------------------------------
    console_handler = RichHandler(
        rich_tracebacks=True,
        show_time=True,
        show_path=False
    )
    console_handler.setLevel(logging.INFO)  # Respect debug toggle if needed

    # ------------------------------------------------------------------
    # Root handler (gedcom_parser.log)
    # ------------------------------------------------------------------
    root_handler = logging.FileHandler(ROOT_LOG_FILE)
    root_handler.setLevel(logging.DEBUG)
    root_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    ))

    # ------------------------------------------------------------------
    # Per-module handler (logs/<module>.log)
    # ------------------------------------------------------------------
    module_log_path = os.path.join(LOG_DIR, f"{name}.log")
    module_handler = logging.FileHandler(module_log_path)
    module_handler.setLevel(logging.DEBUG)
    module_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    ))

    # ------------------------------------------------------------------
    # Attach handlers
    # ------------------------------------------------------------------
    logger.addHandler(console_handler)
    logger.addHandler(root_handler)
    logger.addHandler(module_handler)

    return logger
