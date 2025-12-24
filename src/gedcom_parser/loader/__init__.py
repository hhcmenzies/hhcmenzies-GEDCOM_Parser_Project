# src/gedcom_parser/loader/__init__.py

"""
Public interface for the GEDCOM loader stack.

Intended usage from other parts of the project and tests:

    from gedcom_parser.loader import (
        Token,
        GedcomSyntaxError,
        GEDCOMNode,
        GEDCOMStructureError,
        GEDCOMTree,
        tokenize_file,
        tokenize_line,
        segment_lines,
        segment_records,
        build_tree,
        reconstruct_values,
    )
"""

from __future__ import annotations
from .value_reconstructor import reconstruct_values
from .tokenizer import Token, GedcomSyntaxError, tokenize_file, tokenize_line
from .segmenter import GEDCOMNode, GEDCOMStructureError, segment_lines, segment_records
from .tree_builder import GEDCOMTree, build_tree
from .value_reconstructor import reconstruct_values  # assuming this already exists


__all__ = [
    "Token",
    "GedcomSyntaxError",
    "GEDCOMNode",
    "GEDCOMStructureError",
    "GEDCOMTree",
    "tokenize_file",
    "tokenize_line",
    "segment_lines",
    "segment_records",
    "build_tree",
    "reconstruct_values",
]
