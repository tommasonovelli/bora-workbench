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


def _verify_install(python: Path) -> None:
    """Exercise installed metadata, resources, validation, engine status, and calibration CLI."""
    command = (
        "import hashlib; "
        "from importlib.metadata import version; "
        "from qwen_launcher.resources import read_json, read_text, resource; "
        "assert version('qwen-launcher') == '0.1.0.dev0'; "
        "assert 'Spike 0' in read_text('README.txt'); "
        "lock = read_json('engine.lock'); "
        "assert lock['release'] == 'b10011' and lock['assets_complete']; "
        "assert 'ggml authors' in read_text('notices/llama.cpp-LICENSE'); "
        "assert 'NVIDIA' in read_text('notices/NVIDIA-CUDA-EULA.html'); "
        "assert hashlib.sha256(resource('benchmark-v1/prompt.txt').read_bytes()).hexdigest() == "
        "'1c7182235411da2d4fe6fca130e3effb0b0d965569c52abd8fd45327103ddb2e'; "
        "assert hashlib.sha256(resource('benchmark-v1/request.json').read_bytes()).hexdigest() == "
        "'025dc91aeb61a790d5fd36c27f127e04761ae7f1c3d6b542d0cfd9d37bc5c19f'"
    )
    subprocess.run([str(python), "-c", command], check=True)
    subprocess.run([str(python), "-m", "qwen_launcher.cli", "--version"], check=True)
    subprocess.run([str(python), "-m", "qwen_launcher.cli", "validate"], check=True)
    subprocess.run([str(python), "-m", "qwen_launcher.cli", "engine", "status"], check=True)
    subprocess.run([str(python), "-m", "qwen_launcher.cli", "calibrate", "--help"], check=True)


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
        _verify_install(python)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
