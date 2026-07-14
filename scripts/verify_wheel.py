"""Build-artifact smoke test used by CI."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> int:
    wheels = list(Path("dist").glob("*.whl"))
    if len(wheels) != 1:
        print(f"expected exactly one wheel in dist/, found {len(wheels)}", file=sys.stderr)
        return 1

    uv = shutil.which("uv")
    if uv is None:
        print("uv is required to verify the wheel", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory(prefix="qwen-launcher-wheel-") as directory:
        environment = Path(directory) / "venv"
        subprocess.run([uv, "venv", "--python", "3.12", str(environment)], check=True)
        subprocess.run(
            [uv, "pip", "install", "--python", str(environment), str(wheels[0].resolve())],
            check=True,
        )
        python = environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        command = (
            "from importlib.metadata import version; "
            "from qwen_launcher.resources import read_text; "
            "assert version('qwen-launcher') == '0.1.0.dev0'; "
            "assert 'Spike 0' in read_text('README.txt')"
        )
        subprocess.run([str(python), "-c", command], check=True)
        subprocess.run([str(python), "-m", "qwen_launcher.cli", "--version"], check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
