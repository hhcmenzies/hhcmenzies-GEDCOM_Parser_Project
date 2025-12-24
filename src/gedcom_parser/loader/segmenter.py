# src/gedcom_parser/loader/segmenter.py

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Iterator

from .tokenizer import Token


@dataclass
class GEDCOMNode:
    """
    A hierarchical GEDCOM tree node produced from a flat token stream.

    Attributes:
        level: GEDCOM level number (0 for records, >0 for substructures).
        tag: The GEDCOM tag (HEAD, INDI, BIRT, DATE, NOTE, etc.).
        value: The raw tag value (string).
        pointer: Optional GEDCOM @XREF@ pointer on level-0 records.
        children: Nested GEDCOMNode list ordered as they appeared.
        lineno: Line number in original file (for debugging).
    """

    level: int
    tag: str
    value: str = ""
    pointer: Optional[str] = None
    lineno: int = 0
    children: List["GEDCOMNode"] = field(default_factory=list)

    # ---------- Helper / Mixin Methods ----------

    def add_child(self, child: "GEDCOMNode") -> None:
        self.children.append(child)

    def find_children(self, tag: str) -> List["GEDCOMNode"]:
        """Return all direct children of this node with a given tag."""
        return [c for c in self.children if c.tag == tag]

    def find_first(self, tag: str) -> Optional["GEDCOMNode"]:
        """Return the first direct child with this tag, or None."""
        for c in self.children:
            if c.tag == tag:
                return c
        return None

    def iter_subtree(self) -> Iterator["GEDCOMNode"]:
        """Yield this node and all descendants in depth-first order."""
        yield self
        for child in self.children:
            yield from child.iter_subtree()

    def __repr__(self) -> str:
        ptr = f" {self.pointer}" if self.pointer else ""
        return f"<GEDCOMNode {self.level}{ptr} {self.tag}: {self.value!r}>"


# ---------- SEGMENTER IMPLEMENTATION ----------

class GEDCOMStructureError(Exception):
    """Raised when hierarchical structure rules are violated."""


def segment_lines(tokens: List[Token]) -> List[GEDCOMNode]:
    """
    Convert a flat list of Tokens into a full hierarchical tree.

    Rules:
        - Level 0 tokens are roots.
        - Level N nodes must be children of the nearest previous node
          with level (N-1).
        - Levels may not jump more than +1 (e.g., level 3 cannot follow level 1).

    This function returns ALL nodes, preserving hierarchy.
    Use segment_records() to extract record-level (level 0) nodes only.
    """
    if not tokens:
        return []

    root_nodes: List[GEDCOMNode] = []
    stack: List[GEDCOMNode] = []  # stack[level] = last node at that level

    for tok in tokens:
        node = GEDCOMNode(
            level=tok.level,
            tag=tok.tag,
            value=tok.value,
            pointer=tok.pointer,
            lineno=tok.lineno,
        )

        # Level-0: always a new root
        if tok.level == 0:
            root_nodes.append(node)
            stack = [node]  # reset stack
            continue

        # For non-zero levels:
        # Validate jump constraints (cannot skip levels)
        if tok.level > len(stack):
            raise GEDCOMStructureError(
                f"Line {tok.lineno}: Level jumped from {len(stack)-1} to {tok.level} without intermediate parent"
            )

        # Pop the stack down to parent level
        parent_level = tok.level - 1
        stack = stack[: tok.level]

        if parent_level < 0 or parent_level >= len(stack):
            raise GEDCOMStructureError(
                f"Line {tok.lineno}: No valid parent for level {tok.level}"
            )

        parent = stack[parent_level]
        parent.add_child(node)

        # Push node to stack
        if tok.level == len(stack):
            stack.append(node)
        else:
            stack[tok.level] = node

    return root_nodes


def segment_records(tokens: List[Token]) -> List[GEDCOMNode]:
    """
    Convenience wrapper: build the tree and return only level-0 nodes.
    """
    tree = segment_lines(tokens)
    return tree
