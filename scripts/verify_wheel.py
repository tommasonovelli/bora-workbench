"""Build-artifact smoke test used by CI.

Installs the built wheel into a throwaway environment and exercises it from the outside. That is the
only way to catch what a repository-local test cannot see: resources missing from the wheel, or a
console entry point that never got wired up (specification section 5.1).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path


def _resource_probe() -> str:
    """Return the isolated Python probe for installed metadata and packaged resources."""
    return (
        "import hashlib; "
        "from importlib.metadata import version; "
        "from qwen_launcher.profiles import load_catalog; "
        "from qwen_launcher.resources import read_json, read_text, resource; "
        "assert version('qwen-launcher') == '0.1.0'; "
        "assert 'Spike 0' in read_text('README.txt'); "
        "lock = read_json('engine.lock'); "
        "assert lock['release'] == 'b10011' and lock['assets_complete']; "
        "assert 'ggml authors' in read_text('notices/llama.cpp-LICENSE'); "
        "assert 'NVIDIA' in read_text('notices/NVIDIA-CUDA-EULA.html'); "
        "assert hashlib.sha256(resource('benchmark-v1/prompt.txt').read_bytes()).hexdigest() == "
        "'1c7182235411da2d4fe6fca130e3effb0b0d965569c52abd8fd45327103ddb2e'; "
        "assert hashlib.sha256(resource('benchmark-v1/request.json').read_bytes()).hexdigest() == "
        "'025dc91aeb61a790d5fd36c27f127e04761ae7f1c3d6b542d0cfd9d37bc5c19f'; "
        "policy = read_json('content/calibration-policy.json'); "
        "report_path = 'content/' + policy['evidence'][0]['path']; "
        "report_bytes = resource(report_path).read_bytes(); "
        "assert hashlib.sha256(report_bytes).hexdigest() == policy['evidence'][0]['sha256']; "
        "report = read_json(report_path); "
        "assert report['gate']['overall_status'] == 'gate-partial'; "
        "assert not report['gate']['constants_validated_on_materially_different_hardware']; "
        "assert [(s.mode_id, s.n_cpu_moe) for s in load_catalog().calibration_seeds] == "
        "[('coding', 37), ('studio', 37), ('vstudio', 39)]"
    )


def _verify_install(python: Path, environment: dict[str, str]) -> None:
    """Exercise installed metadata, resources, validation, engine status, and calibration CLI."""
    subprocess.run([str(python), "-c", _resource_probe()], check=True, env=environment)
    subprocess.run(
        [str(python), "-m", "qwen_launcher.cli", "--version"], check=True, env=environment
    )
    subprocess.run(
        [str(python), "-m", "qwen_launcher.cli", "validate"], check=True, env=environment
    )
    subprocess.run(
        [str(python), "-m", "qwen_launcher.cli", "engine", "status"],
        check=True,
        env=environment,
    )
    subprocess.run(
        [str(python), "-m", "qwen_launcher.cli", "calibrate", "--help"],
        check=True,
        env=environment,
    )


def _isolated_environment(root: Path) -> dict[str, str]:
    """Redirect every public root so wheel verification never reads user state (section 5.2)."""
    environment = dict(os.environ)
    environment.update(
        {
            "APPDATA": str(root / "roaming"),
            "LOCALAPPDATA": str(root / "local"),
            "XDG_CACHE_HOME": str(root / "cache"),
            "XDG_CONFIG_HOME": str(root / "config"),
            "XDG_DATA_HOME": str(root / "data"),
            "XDG_STATE_HOME": str(root / "state"),
        }
    )
    return environment


def _verify_sdist() -> bool:
    """Require one sdist containing the installers and release documentation."""
    archives = list(Path("dist").glob("*.tar.gz"))
    if len(archives) != 1:
        print(f"expected exactly one sdist in dist/, found {len(archives)}", file=sys.stderr)
        return False
    required = (
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        "IMPLEMENTATION_SPEC.md",
        "docs/anatomy/mode.md",
        "docs/anatomy/profile.md",
        "docs/benchmarks.md",
        "docs/releasing.md",
        "docs/troubleshooting.md",
        "install.ps1",
        "install.sh",
    )
    try:
        with tarfile.open(archives[0], "r:gz") as archive:
            members = archive.getmembers()
    except (OSError, tarfile.TarError) as error:
        print(f"could not inspect sdist: {error}", file=sys.stderr)
        return False
    names = tuple(member.name for member in members)
    missing = [path for path in required if not any(name.endswith(f"/{path}") for name in names)]
    if missing:
        print(f"sdist is missing: {', '.join(missing)}", file=sys.stderr)
        return False
    return True


def main() -> int:
    """Install the wheel in isolation and inspect both release distributions."""
    # Globbing in Python rather than in the shell keeps this identical on Ubuntu and Windows. An
    # ambiguous dist/ is refused outright, so a stale wheel can never be the one CI blesses.
    wheels = list(Path("dist").glob("*.whl"))
    if len(wheels) != 1:
        print(f"expected exactly one wheel in dist/, found {len(wheels)}", file=sys.stderr)
        return 1
    if not _verify_sdist():
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
        _verify_install(python, _isolated_environment(Path(directory) / "user-roots"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
