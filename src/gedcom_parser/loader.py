"""
File loader and dispatcher.

Eventually supports:
- GEDCOM (.ged)
- JSON exports
- CSV inventories
- Database ingestion
"""

import os

def load_file(path: str):
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")

    print(f"Loaded file: {path}")
    # Future: return parsed structure depending on extension
