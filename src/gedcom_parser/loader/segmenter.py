"""
GEDCOM record segmentation and pointer indexing.

Takes the flat tree (from tree_builder) and:
- Groups top-level records (level 0) by TAG (INDI, FAM, SOUR, REPO, etc.).
- Builds a pointer index mapping @X...@ -> list of nodes that reference it.

This is intentionally generic and read-only: it does not mutate the tree.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple


Node = Dict[str, Any]
Tree = List[Node]


def segment_top_level(tree: Tree) -> Dict[str, List[Node]]:
    """
    Group top-level (level 0) records by their TAG.

    Example result keys:
        "HEAD", "INDI", "FAM", "SOUR", "REPO", "NOTE", "TRLR", etc.
    """
    sections: Dict[str, List[Node]] = {}

    for node in tree:
        if node.get("level") != 0:
            continue
        tag = node.get("tag") or "UNKNOWN"
        sections.setdefault(tag, []).append(node)

    return sections


def summarize_top_level(tree: Tree) -> Dict[str, int]:
    """
    Return a simple summary: TAG -> count of level-0 records.
    """
    summary: Dict[str, int] = {}
    for node in tree:
        if node.get("level") != 0:
            continue
        tag = node.get("tag") or "UNKNOWN"
        summary[tag] = summary.get(tag, 0) + 1
    return summary


def build_pointer_index(tree: Tree) -> Dict[str, List[Node]]:
    """
    Build a global index of all nodes that carry a GEDCOM pointer value.

    Pointers look like:
        @I1@       (individual)
        @F12@      (family)
        @S416073157@  (source)
        @R305860344@  (repository)

    The same pointer might appear multiple times (definition + references),
    so the value is always a list.
    """
    index: Dict[str, List[Node]] = {}

    for node in tree:
        pointer = node.get("pointer")
        if not pointer:
            continue
        index.setdefault(pointer, []).append(node)

    return index


def summarize_pointer_index(index: Dict[str, List[Node]]) -> Dict[str, int]:
    """
    Reduce the pointer index to: pointer -> occurrence count.
    """
    return {ptr: len(nodes) for ptr, nodes in index.items()}


def summarize_pointer_prefixes(index: Dict[str, List[Node]]) -> Dict[str, int]:
    """
    Quick sanity view of pointer "types" by first character after '@'.

    Examples:
        @I1@  -> 'I' (individual)
        @F12@ -> 'F' (family)
        @S... -> 'S' (source)
        @R... -> 'R' (repository)

    Returns a mapping like:
        {"I": 1234, "F": 456, "S": 789, "R": 12}
    """
    prefix_counts: Dict[str, int] = {}

    for ptr, nodes in index.items():
        if len(ptr) >= 3 and ptr[0] == "@" and "@" in ptr[1:]:
            # take first char after initial '@'
            second_at = ptr.rfind("@")
            if second_at > 1:
                prefix = ptr[1]
            else:
                prefix = "?"
        else:
            prefix = "?"

        prefix_counts[prefix] = prefix_counts.get(prefix, 0) + len(nodes)

    return prefix_counts
