"""
GEDCOM Value Reconstruction
---------------------------

Rebuilds multi-line values using CONC and CONT tags.
"""

from typing import List, Dict, Any


def reconstruct_values(tree: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Walk the entire GEDCOM tree and merge multiline values.

    Rules:
    - CONC: append text directly
    - CONT: append newline + text
    """

    for node in tree:
        _process_node(node)

    return tree


def _process_node(node: Dict[str, Any]):
    """
    Recursively process this node and its children.
    """

    children = node.get("children", [])
    if not children:
        return

    new_children = []
    buffer_value = node.get("value", "")

    for child in children:
        tag = child["tag"]

        if tag == "CONC":
            buffer_value += child["value"]
            continue

        if tag == "CONT":
            buffer_value += "\n" + child["value"]
            continue

        # Non-CONC/CONT child passes through
        new_children.append(child)
        _process_node(child)

    node["value"] = buffer_value
    node["children"] = new_children
