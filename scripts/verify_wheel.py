"""Build-artifact smoke test used by CI.

Installs the built wheel into a throwaway environment and exercises it from the outside. That is the
only way to catch what a repository-local test cannot see: resources missing from the wheel, or a
console entry point that never got wired up (specification section 5.1).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> int:
    """Install the wheel in an isolated environment and verify it, returning a process exit code."""
    # Globbing in Python rather than in the shell keeps this identical on Ubuntu and Windows. An
    # ambiguous dist/ is refused outright, so a stale wheel can never be the one CI blesses.
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
        # Runs inside the isolated interpreter, so the checks travel as source text. Step 2B adds
        # installed-content validation to the import, resource, and version checks.
        command = (
            "from importlib.metadata import version; "
            "from qwen_launcher.resources import read_json, read_text; "
            "assert version('qwen-launcher') == '0.1.0.dev0'; "
            "assert 'Spike 0' in read_text('README.txt'); "
            "assert read_json('engine.lock')['release'] == 'b10011'"
        )
        subprocess.run([str(python), "-c", command], check=True)
        subprocess.run([str(python), "-m", "qwen_launcher.cli", "--version"], check=True)
        subprocess.run([str(python), "-m", "qwen_launcher.cli", "validate"], check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
