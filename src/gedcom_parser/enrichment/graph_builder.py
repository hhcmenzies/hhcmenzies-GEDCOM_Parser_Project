"""
C.24.4.8.1 — Graph Schema & Builder Skeleton

Defines:
- Graph data model
- Node & edge constructors
- Base build_graph() function (logic filled in later in 8.2)
- CLI wrapper

This module does NOT yet build a full graph.
It only provides the framework and validated data structures.

Next steps:
- C.24.4.8.2: full graph construction
- C.24.4.8.3: graph integrity tests
"""

from __future__ import annotations

import argparse
import json
from typing import Any, Dict, List, Optional, Literal
from dataclasses import dataclass, field
from pathlib import Path


# ======================================================================
# NODE & EDGE DATA MODELS
# ======================================================================

NodeType = Literal[
    "INDI", "FAM", "EVENT", "PLACE", "SOURCE", "REPO", "OBJE"
]

EdgeType = Literal[
    "PARENT",
    "SPOUSE",
    "EVENT_OF",
    "PLACE_OF",
    "SOURCE_OF",
    "REFERENCE",
]


@dataclass
class GraphNode:
    """
    Generic graph node.

    All nodes MUST have:
    - uuid (unique identifier, stable)
    - type (INDI, FAM, EVENT, PLACE, etc.)
    - label (human-readable)
    - data (arbitrary dict)
    """
    uuid: str
    type: NodeType
    label: str
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    """
    Graph edge between two nodes.

    All edges have:
    - from_uuid
    - to_uuid
    - type (PARENT, SPOUSE, EVENT_OF, etc.)
    """
    from_uuid: str
    to_uuid: str
    type: EdgeType
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Graph:
    """
    Complete graph container.
    """
    nodes: Dict[str, GraphNode] = field(default_factory=dict)
    edges: List[GraphEdge] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)


# ======================================================================
# GRAPH CONSTRUCTION API (FOUNDATION ONLY)
# ======================================================================

def add_node(graph: Graph, node: GraphNode) -> None:
    """Insert or replace a node."""
    graph.nodes[node.uuid] = node


def add_edge(graph: Graph, edge: GraphEdge) -> None:
    """Append an edge."""
    graph.edges.append(edge)


def build_graph(xref_data: Dict[str, Any]) -> Graph:
    """
    Primary entry for building a global genealogical graph.

    ***This is a skeleton only.***
    Real logic is implemented in C.24.4.8.2.

    For now, we only create:
        graph = Graph(meta={ "source": "xref", "version": 1 })

    And return it untouched.
    """
    graph = Graph(
        nodes={},
        edges=[],
        meta={
            "source": "xref",
            "version": 1,
        }
    )

    # -------------------------------------------------------------
    # Full population of nodes and edges occurs in 8.2.
    # -------------------------------------------------------------
    return graph


# ======================================================================
# FILE I/O
# ======================================================================

def load_xref(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_graph(graph: Graph, path: str) -> None:
    out = {
        "meta": graph.meta,
        "nodes": {uuid: node.__dict__ for uuid, node in graph.nodes.items()},
        "edges": [edge.__dict__ for edge in graph.edges],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)


# ======================================================================
# CLI ENTRY POINT
# ======================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="C.24.4.8 — Graph Builder"
    )
    parser.add_argument("input", help="xref-enhanced JSON file")
    parser.add_argument(
        "-o", "--output",
        default="outputs/export_graph.json",
        help="Output graph JSON path"
    )

    args = parser.parse_args()

    xref_data = load_xref(args.input)
    graph = build_graph(xref_data)
    save_graph(graph, args.output)

    print(f"[INFO] Graph skeleton written to: {args.output}")


if __name__ == "__main__":
    main()
