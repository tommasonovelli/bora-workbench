"""Tests for the package import side-effect boundary."""

import os
import subprocess
import sys
from pathlib import Path


def test_import_has_no_filesystem_side_effects(tmp_path) -> None:
    """Import the package in an empty root without creating any path."""
    source_root = Path(__file__).parents[1] / "src"
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(source_root)
    subprocess.run(
        [sys.executable, "-c", "import bora_workbench"],
        cwd=tmp_path,
        env=environment,
        check=True,
    )
    assert not any(tmp_path.iterdir())
