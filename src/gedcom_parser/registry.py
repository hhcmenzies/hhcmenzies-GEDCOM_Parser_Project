"""
Unified Runtime Registry
Phase 1 – Step 2

Central shared registry for:
- Global configuration (yaml)
- Normalization datasets
- TAG metadata
- Output directory helpers
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any

from gedcom_parser.config import get_config
from gedcom_parser.logging import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------
# Registry Object
# ---------------------------------------------------------------------

class GPRegistry:
    """Singleton container for shared config + datasets."""

    def __init__(self):
        self.config = get_config()
        self._datasets: Dict[str, Dict[str, Any]] = {}
        self._tag_meta: Dict[str, Dict[str, Any]] = {}

    # -------------------------------
    # Dataset Loader
    # -------------------------------
    def get_dataset(self, name: str) -> Dict[str, Any]:
        if name in self._datasets:
            return self._datasets[name]

        dataset_path = Path(__file__).resolve().parents[2] / "datasets" / f"{name}.json"

        if not dataset_path.exists():
            log.warning(f"Dataset not found: {dataset_path}")
            self._datasets[name] = {}
            return {}

        try:
            with open(dataset_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._datasets[name] = data
            log.info(f"Loaded dataset: {dataset_path.name}")
            return data
        except Exception as e:
            log.error(f"Failed loading dataset {dataset_path}: {e}")
            self._datasets[name] = {}
            return {}

    # -------------------------------
    # Tag Metadata Loader
    # -------------------------------
    def get_tag_meta(self, tag: str) -> Dict[str, Any]:
        if tag in self._tag_meta:
            return self._tag_meta[tag]

        path = Path(__file__).resolve().parents[2] / "config" / "tag_metadata.json"

        if not path.exists():
            log.warning(f"No tag metadata file: {path}")
            return {}

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self._tag_meta = data
            return data.get(tag, {})
        except Exception as e:
            log.error(f"Error reading tag metadata: {e}")
            return {}

# ---------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------

_registry: GPRegistry | None = None

def get_registry() -> GPRegistry:
    global _registry
    if _registry is None:
        _registry = GPRegistry()
    return _registry

# ---------------------------------------------------------------------
# Helper top-level functions
# ---------------------------------------------------------------------

def get_output_dir() -> Path:
    reg = get_registry()
    p = reg.config.paths.get("output_dir", "outputs")
    return Path(p)

def get_input_path() -> Path:
    reg = get_registry()
    p = reg.config.paths.get("input", "input.ged")
    return Path(p)

def get_normalization_dataset(name: str) -> Dict[str, Any]:
    return get_registry().get_dataset(name)

def get_tag_meta(tag: str) -> Dict[str, Any]:
    return get_registry().get_tag_meta(tag)

