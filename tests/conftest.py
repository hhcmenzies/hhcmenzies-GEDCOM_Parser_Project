import sys
from pathlib import Path

# Ensure the project src directory is on sys.path for test imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_PATH = PROJECT_ROOT / "src"
if SRC_PATH not in sys.path:
    sys.path.insert(0, str(SRC_PATH))
