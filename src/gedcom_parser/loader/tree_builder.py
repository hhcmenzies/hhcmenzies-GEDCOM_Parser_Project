# src/gedcom_parser/loader/tree_builder.py

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, Iterator, List, Optional

from .tokenizer import Token
from .segmenter import GEDCOMNode, segment_records


@dataclass
class GEDCOMTree:
    """
    High-level wrapper around a list of top-level GEDCOMNode records.

    This structure is the canonical representation of a parsed GEDCOM file
    for downstream components (entity extraction, registry building, etc.).

    Attributes:
        records:
            A list of level-0 GEDCOMNode instances (HEAD, INDI, FAM, SOUR,
            REPO, NOTE, OBJE, TRLR, and any other level-0 records).
    """

    records: List[GEDCOMNode]

    # Internal indexes, built lazily
    _pointer_index: Dict[str, GEDCOMNode] = field(
        default_factory=dict, init=False, repr=False
    )
    _tag_index: Dict[str, List[GEDCOMNode]] = field(
        default_factory=dict, init=False, repr=False
    )
    _indexes_built: bool = field(default=False, init=False, repr=False)

    # ------------------------------------------------------------------ #
    # Core helpers
    # ------------------------------------------------------------------ #

    def __len__(self) -> int:  # pragma: no cover - trivial wrapper
        return len(self.records)

    def __iter__(self) -> Iterator[GEDCOMNode]:  # pragma: no cover - simple
        return iter(self.records)

    def iter_nodes(self) -> Iterator[GEDCOMNode]:
        """
        Iterate over every node in the tree (depth-first), including roots
        and all descendants.
        """
        for root in self.records:
            yield from root.iter_subtree()

    # ------------------------------------------------------------------ #
    # Index construction
    # ------------------------------------------------------------------ #

    def _build_indexes(self) -> None:
        """Build pointer and tag indexes from the current records."""
        pointer_index: Dict[str, GEDCOMNode] = {}
        tag_index: Dict[str, List[GEDCOMNode]] = {}

        for node in self.iter_nodes():
            # Pointer index
            if node.pointer:
                pointer_index[node.pointer] = node

            # Tag index (case-insensitive, store uppercase)
            tag = (node.tag or "").upper()
            if not tag:
                continue
            tag_index.setdefault(tag, []).append(node)

        self._pointer_index = pointer_index
        self._tag_index = tag_index
        self._indexes_built = True

    def _ensure_indexes(self) -> None:
        if not self._indexes_built:
            self._build_indexes()

    # ------------------------------------------------------------------ #
    # Public query API
    # ------------------------------------------------------------------ #

    def find_by_pointer(self, pointer: str) -> Optional[GEDCOMNode]:
        """
        Return the node with the given @XREF@ pointer, if any.

        Args:
            pointer: e.g. '@I1@', '@F5@', etc.

        Returns:
            GEDCOMNode or None.
        """
        if not pointer:
            return None
        self._ensure_indexes()
        return self._pointer_index.get(pointer)

    def find_records_by_tag(self, tag: str) -> List[GEDCOMNode]:
        """
        Return all level-0 records with the given tag (case-insensitive).

        Args:
            tag: e.g. 'HEAD', 'INDI', 'FAM'.

        Returns:
            List of GEDCOMNode instances at level 0.
        """
        if not tag:
            return []
        self._ensure_indexes()
        t = tag.upper()
        candidates = self._tag_index.get(t, [])
        return [n for n in candidates if n.level == 0]

    def all_tags(self) -> List[str]:
        """
        Return a list of distinct tags found among level-0 records.
        """
        tags = {rec.tag for rec in self.records if rec.tag}
        return sorted(tags)

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"<GEDCOMTree records={len(self.records)}>"
    

def build_tree(tokens: Iterable[Token]) -> GEDCOMTree:
    """
    Build a GEDCOMTree from a token stream.

    This function is the main entry point for the loader pipeline:

        tokens -> GEDCOMTree(records=[GEDCOMNode, ...])

    Downstream components (value reconstruction, entity extraction, etc.)
    should operate on this tree.
    """
    # We materialize tokens into a list because segment_records needs
    # random access to levels. For very large files, a streaming variant
    # could be introduced later.
    token_list = list(tokens)
    records = segment_records(token_list)
    return GEDCOMTree(records=records)
