from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ParseContext:
    """
    Shared pipeline context.
    This object is passed between orchestration layers.
    """

    config: Any
    logger: Any

    input_path: Optional[str] = None
    output_path: Optional[str] = None

    stats: Dict[str, Any] = field(default_factory=dict)
    errors: list = field(default_factory=list)

    debug: bool = False
