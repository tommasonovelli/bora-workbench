import os
import subprocess
import sys
from pathlib import Path


def test_import_has_no_filesystem_side_effects(tmp_path):
    source_root = Path(__file__).parents[1] / "src"
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(source_root)
    subprocess.run(
        [sys.executable, "-c", "import qwen_launcher"],
        cwd=tmp_path,
        env=environment,
        check=True,
    )
    assert not any(tmp_path.iterdir())
