from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional


def _load_yaml(path: Path) -> Dict[str, Any]:
    try:
        import yaml  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "PyYAML is required for config loading. Install with: pip install pyyaml"
        ) from e

    if not path.exists():
        return {}

    data = yaml.safe_load(path.read_text(encoding="utf-8"))  # type: ignore[attr-defined]
    return data if isinstance(data, dict) else {}


def get_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load project configuration.

    Resolution order:
      1) explicit `config_path` argument
      2) env var GEDCOM_CONFIG
      3) config/processing_config.yml
      4) config/gedcom_parser.yml

    Returns an empty dict if no config file exists.
    """
    root = Path(__file__).resolve().parents[2]  # .../src/gedcom_parser -> project root

    candidates = []
    if config_path:
        candidates.append(Path(config_path))
    env_path = os.getenv("GEDCOM_CONFIG")
    if env_path:
        candidates.append(Path(env_path))

    candidates.append(root / "config" / "processing_config.yml")
    candidates.append(root / "config" / "gedcom_parser.yml")

    for p in candidates:
        cfg = _load_yaml(p)
        if cfg:
            # Optional breadcrumb so callers can record which file was used
            cfg.setdefault("_meta", {})
            if isinstance(cfg["_meta"], dict):
                cfg["_meta"].setdefault("config_path", str(p))
            return cfg

    return {}
