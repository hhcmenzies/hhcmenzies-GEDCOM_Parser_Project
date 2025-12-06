"""
parser_core.py
Central parsing engine with full logging integration.
"""

from __future__ import annotations
from typing import Any, Dict, List

from gedcom_parser.config import get_config
from gedcom_parser.logger import get_logger
from gedcom_parser.loader.tokenizer import tokenize_file
from gedcom_parser.loader.tree_builder import build_tree
from gedcom_parser.loader.value_reconstructor import reconstruct_values
from gedcom_parser.entities.registry import build_entity_registry


class GEDCOMParser:
    """
    High-level parser:
      - loads file
      - tokenizes
      - reconstructs values
      - builds tree
      - builds entity registry
    """

    def __init__(self, config=None):
        self.cfg = config if config is not None else get_config()
        self.log = get_logger("parser_core")

        self.tokens: List[Dict[str, Any]] = []
        self.roots: List[Dict[str, Any]] = []
        self.entity_registry = None

        self.log.info("Parser engine initialized.")

    # ---------------------------------------------------------
    # Load file
    # ---------------------------------------------------------
    def load_file(self, path: str) -> None:
        """Tokenize GEDCOM input into list of tokens."""
        self.log.info(f"Tokenizing GEDCOM input: {path}")
        try:
            # FORCE materialization of generator
            self.tokens = list(tokenize_file(path))
        except Exception:
            self.log.exception("Tokenization failed.")
            raise

        if self.cfg.debug:
            self.log.debug(f"Token count = {len(self.tokens)}")

    # ---------------------------------------------------------
    # Reconstruct + Build Tree + Extract Entities
    # ---------------------------------------------------------
    def run(self, input_path: str):
        """
        Full parse sequence.
        Returns: entity_registry
        """
        self.load_file(input_path)

        self.log.info("Running parser engine...")

        try:
            # tree builder now accepts LIST
            self.roots = build_tree(self.tokens)
            reconstruct_values(self.roots)

            # Build entity registry
            self.entity_registry = build_entity_registry(self.roots)
            self.log.info("Parser run completed. Registry ready.")

            return self.entity_registry

        except Exception:
            self.log.exception("Parser run failed.")
            raise
