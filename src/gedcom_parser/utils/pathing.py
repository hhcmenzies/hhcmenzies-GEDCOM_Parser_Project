# src/gedcom_parser/utils/pathing.py

from __future__ import annotations

from pathlib import Path
from typing import Union


# We assume this file lives at:
#   <project_root>/src/gedcom_parser/utils/pathing.py
#
# Path(__file__).resolve().parents gives:
#   [0] .../src/gedcom_parser/utils
#   [1] .../src/gedcom_parser
#   [2] .../src
#   [3] .../ (project root)
#
# If your layout differs, adjust the index (3) accordingly.
_PROJECT_ROOT = Path(__file__).resolve().parents[3]


def project_root() -> Path:
    """
    Return the absolute path to the project root directory.

    The project root is defined as the directory that contains:
      - src/
      - tests/
      - config/
      - mock_files/
    """
    return _PROJECT_ROOT


def resolve_project_path(relative: Union[str, Path]) -> Path:
    """
    Resolve a path relative to the project root.

    Examples:
        resolve_project_path("mock_files/gedcom_1.ged")
        resolve_project_path(Path("tests") / "data" / "foo.txt")
    """
    return project_root() / Path(relative)


def mock_file_path(filename: Union[str, Path]) -> Path:
    """
    Return the absolute path to a file under the top-level mock_files/ directory.
    """
    return resolve_project_path(Path("mock_files") / filename)


def tests_data_path(*parts: Union[str, Path]) -> Path:
    """
    Return the absolute path to a file under tests/data/.

    Examples:
        tests_data_path("valid", "minimal_55.ged")
        tests_data_path("expected_json", "minimal_55.json")
    """
    return resolve_project_path(Path("tests") / "data" / Path(*parts))
