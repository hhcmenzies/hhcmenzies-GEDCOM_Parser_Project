from __future__ import annotations

import os
import sys
from pathlib import Path

from gedcom_parser.config import get_config


def doctor_command() -> None:
    """
    Validate environment and basic project wiring.
    Keep this lightweight and deterministic.
    """
    project_root = Path(__file__).resolve().parents[4]

    checks = []

    # Python
    checks.append(("python_executable", sys.executable))
    checks.append(("python_version", sys.version.split()[0]))

    # Editable install sanity
    try:
        import gedcom_parser  # noqa: F401
        checks.append(("import gedcom_parser", "OK"))
    except Exception as e:
        checks.append(("import gedcom_parser", f"FAIL: {e!r}"))

    # YAML
    try:
        import yaml  # noqa: F401
        checks.append(("import pyyaml", "OK"))
    except Exception as e:
        checks.append(("import pyyaml", f"FAIL: {e!r}"))

    # Config load
    try:
        cfg = get_config()
        meta = cfg.get("_meta", {})
        checks.append(("get_config()", "OK"))
        checks.append(("config_path", meta.get("config_path", "(unknown)")))
    except Exception as e:
        checks.append(("get_config()", f"FAIL: {e!r}"))

    # Expected directories (adjust later as your contract hardens)
    for rel in ["config", "src", "db", "_docs", "tests"]:
        p = project_root / rel
        checks.append((f"exists: {rel}", "OK" if p.exists() else "MISSING"))

    # Environment vars that often matter on Windows
    checks.append(("PYTHONPATH", os.environ.get("PYTHONPATH", "")))

    # Print
    width = max(len(k) for k, _ in checks)
    for k, v in checks:
        print(f"{k:<{width}}  {v}")
