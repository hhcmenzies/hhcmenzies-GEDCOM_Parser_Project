import os
from rich import print as rprint

def load_file(path: str):
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")

    rprint(f"[green][INFO][/green] Loaded file: {path}")

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()
