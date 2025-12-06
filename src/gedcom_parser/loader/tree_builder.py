"""
GEDCOM Hierarchical Tree Builder
--------------------------------

Converts a flat token stream (from tokenizer)
into a nested tree structure.

Each root node is a level-0 record (INDI, FAM, SOUR, REPO, HEAD, TRLR).
Children are attached based on level increases.
"""

from typing import List, Dict, Any, Optional


def build_tree(tokens: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Build a hierarchical tree of GEDCOM records.
    Returns a list of top-level records.
    """

    root_records = []
    stack: List[Dict[str, Any]] = []  # Stack to track parent nodes

    for token in tokens:
        node = {
            "level": token["level"],
            "tag": token["tag"],
            "value": token.get("value", ""),
            "pointer": token.get("pointer"),
            "children": [],
            "lineno": token.get("lineno"),
        }

        level = token["level"]

        # Level 0 means a new top-level record
        if level == 0:
            root_records.append(node)
            stack = [node]
            continue

        # Find the correct parent for this level
        # Pop until top of stack is parent level
        while stack and stack[-1]["level"] >= level:
            stack.pop()

        if not stack:
            # Malformed GEDCOM (rare but possible)
            root_records.append(node)
            stack = [node]
            continue

        # Attach as child to parent
        parent = stack[-1]
        parent["children"].append(node)

        # Push to stack
        stack.append(node)

    return root_records
