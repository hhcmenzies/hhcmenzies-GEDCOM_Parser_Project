import yaml
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "gedcom_parser.yml"

class GPConfig:
    def __init__(self, data):
        self.paths = data.get("paths", {})
        self.pipeline = data.get("pipeline", {})
        self.logging = data.get("logging", {})
        self.debug = data.get("debug", False)

def load_config() -> 'GPConfig':
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Config file not found: {CONFIG_PATH}")

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    return GPConfig(data)

_config_cache = None

def get_config() -> 'GPConfig':
    global _config_cache
    if _config_cache is None:
        _config_cache = load_config()
    return _config_cache
