from __future__ import annotations

import importlib.metadata
import subprocess
from pathlib import Path
from typing import Optional


def _git_sha(project_root: Path) -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return None


def version_command() -> None:
    """
    Print application + environment version details.
    """
    # package name as installed by pip (see your pip output)
    pkg_name = "gedcom-parser-project"
    try:
        pkg_version = importlib.metadata.version(pkg_name)
    except importlib.metadata.PackageNotFoundError:
        pkg_version = "(not installed as a package; run: pip install -e .)"

    project_root = Path(__file__).resolve().parents[4]  # .../src/gedcom_parser/cli/commands/version.py
    sha = _git_sha(project_root)

    print(f"package: {pkg_name} {pkg_version}")
    if sha:
        print(f"git: {sha}")
    print(f"project_root: {project_root}")
