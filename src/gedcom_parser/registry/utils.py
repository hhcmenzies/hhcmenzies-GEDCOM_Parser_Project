from __future__ import annotations

from typing import Any, Dict, Optional


def _iter_children(node):
    """Yield child GEDCOMNodes safely."""
    return getattr(node, "children", []) or []


def _child_nodes_by_tag(node, tag: str):
    return [c for c in _iter_children(node) if getattr(c, "tag", None) == tag]


def _first_child_value(node, tag: str) -> Optional[str]:
    for c in _iter_children(node):
        if getattr(c, "tag", None) == tag:
            return getattr(c, "value", None)
    return None


def _node_to_event_dict(node) -> Dict[str, Any]:
    """
    Adapt a GEDCOMNode into the dict shape expected by extract_events_from_record().
    Boundary adapter so Phase 3 event extraction remains unchanged.
    """
    return {
        "tag": getattr(node, "tag", None),
        "value": getattr(node, "value", None),
        "pointer": getattr(node, "pointer", None),
        "lineno": getattr(node, "lineno", None),
        "children": [_node_to_event_dict(c) for c in _iter_children(node)],
    }
