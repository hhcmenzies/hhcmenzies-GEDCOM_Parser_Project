# src/gedcom_parser/loader/value_reconstructor.py

"""
Value Reconstructor: Handles GEDCOM CONT / CONC tags.

Rules (GEDCOM 5.5.1 / 5.5.5):
    - CONC: Append text directly to the parent's value.
            No newline added.

    - CONT: Append a newline + the text.
            Always produces a new line in the logical output.

Examples:
    Parent NOTE value: "Line one"
    Child CONC value:  " and more"
        → "Line one and more"

    Child CONT value:  "Second line"
        → "Line one and more\nSecond line"

This module walks the GEDCOMNode tree (from segmenter) and reconstructs
all values according to these rules, removing CONC/CONT nodes afterwards.
"""

from __future__ import annotations

from typing import List

from .segmenter import GEDCOMNode


def _reconstruct_node(node: GEDCOMNode) -> None:
    """
    Recursively reconstruct values for this node and its children.
    Mutates the node in place.

    After reconstruction:
      - Parent.value has the final reconstructed text
      - CONC and CONT child nodes are removed
      - Other children remain and are also processed
    """
    new_children: List[GEDCOMNode] = []
    base_value = node.value or ""

    for child in node.children:
        tag = (child.tag or "").upper()

        if tag == "CONC":
            # Append directly (no newline)
            if child.value:
                base_value += child.value

        elif tag == "CONT":
            # Append newline + child text
            base_value += "\n"
            if child.value:
                base_value += child.value

        else:
            # Normal GEDCOM child; recurse into it
            _reconstruct_node(child)
            new_children.append(child)

    # Apply the reconstructed value
    node.value = base_value
    node.children = new_children


def reconstruct_values(records: List[GEDCOMNode]) -> List[GEDCOMNode]:
    """
    Reconstruct all values for every top-level record and its descendants.

    Args:
        records: The list of root GEDCOMNode objects (level-0 records).

    Returns:
        The same list (records), after in-place reconstruction.

    This is a pure transformation: structure is unchanged except for
    removal of CONC/CONT nodes.
    """
    for rec in records:
        _reconstruct_node(rec)

    return records
