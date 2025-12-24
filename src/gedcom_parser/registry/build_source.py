from __future__ import annotations

from gedcom_parser.loader.tree_builder import GEDCOMNode
from gedcom_parser.identity.uuid_factory import uuid_for_pointer
from gedcom_parser.registry.entities import SourceEntity, GenericAttribute
from gedcom_parser.attachments import extract_attached_records


def build_source(node: GEDCOMNode) -> SourceEntity:
    """
    Build a SourceEntity from a GEDCOMNode with tag 'SOUR'.

    PURE FUNCTION:
      - no registry access
      - no promotion
      - no cross-entity linking

    Handles:
      - inline PAGE / DATA / WWW
      - inline OBJE (captured as attachments, not promoted)
      - custom tags (_APID, etc.) losslessly
    """
    if node.tag != "SOUR":
        raise ValueError(f"Expected SOUR node, got {node.tag}")

    if not node.pointer:
        raise ValueError("SOUR node is missing pointer")

    source = SourceEntity(
        uuid=uuid_for_pointer(node.pointer),
        pointer=node.pointer,
    )

    # Attachments (Step 4: extract only, no promotion)
    source.attachments.extend(
        extract_attached_records(source, node)
    )

    for child in node.children or []:
        tag = child.tag

        if tag == "TITL":
            source.title = child.value

        elif tag == "AUTH":
            source.author = child.value

        elif tag == "PUBL":
            source.publication = child.value

        elif tag == "REPO":
            source.repository_pointer = child.pointer

        elif tag == "NOTE" and child.value:
            source.notes.append(child.value)

        elif tag == "OBJE":
            # Already handled by attachment extractor
            continue

        else:
            # Preserve structured or custom tags (PAGE, DATA, WWW, _APID, etc.)
            source.attributes.append(
                GenericAttribute(
                    tag=tag,
                    value=child.value,
                    pointer=child.pointer,
                    children=[
                        {
                            "tag": c.tag,
                            "value": c.value,
                            "pointer": c.pointer,
                        }
                        for c in (child.children or [])
                    ],
                    lineno=getattr(child, "lineno", None),
                )
            )

    return source
