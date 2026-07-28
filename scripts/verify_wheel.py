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
        "from bora_workbench.profiles import load_catalog; "
        "from bora_workbench.resources import read_json, read_text, resource; "
        "assert version('bora-workbench') == '0.3.1'; "
        "assert 'Spike 0' in read_text('README.txt'); "
        "lock = read_json('engine.lock'); "
        "assert lock['release'] == 'b10011' and lock['assets_complete']; "
        "assert 'ggml authors' in read_text('notices/llama.cpp-LICENSE'); "
        "assert 'NVIDIA' in read_text('notices/NVIDIA-CUDA-EULA.html'); "
        "assert hashlib.sha256(resource('benchmark-v1/prompt.txt').read_bytes()).hexdigest() == "
        "'1c7182235411da2d4fe6fca130e3effb0b0d965569c52abd8fd45327103ddb2e'; "
        "assert hashlib.sha256(resource('benchmark-v1/request.json').read_bytes()).hexdigest() == "
        "'025dc91aeb61a790d5fd36c27f127e04761ae7f1c3d6b542d0cfd9d37bc5c19f'; "
        "record_schema = read_json('schemas/calibration-record.v6.json'); "
        "assert record_schema['properties']['calibration_protocol']['const'] == 'calibration'; "
        "assert record_schema['properties']['reserves']['required'] "
        "== ['vram_gib', 'ram_gib', 'release_tolerance_gib']; "
        "policy = read_json('content/calibration-policy.json'); "
        "report_path = 'content/' + policy['evidence'][0]['path']; "
        "report_bytes = resource(report_path).read_bytes(); "
        "assert hashlib.sha256(report_bytes).hexdigest() == policy['evidence'][0]['sha256']; "
        "report = read_json(report_path); "
        "assert report['gate']['overall_status'] == 'gate-partial'; "
        "assert not report['gate']['constants_validated_on_materially_different_hardware']; "
        "assert [mode.id for mode in load_catalog().modes] == ['coding', 'studio', 'vstudio']"
    )


def _verify_install(python: Path, environment: dict[str, str]) -> None:
    """Exercise installed metadata, resources, validation, engine status, and calibration CLI."""
    subprocess.run([str(python), "-c", _resource_probe()], check=True, env=environment)
    subprocess.run(
        [str(python), "-m", "bora_workbench.cli", "--version"], check=True, env=environment
    )
    subprocess.run(
        [str(python), "-m", "bora_workbench.cli", "validate"], check=True, env=environment
    )
    subprocess.run(
        [str(python), "-m", "bora_workbench.cli", "engine", "status"],
        check=True,
        env=environment,
    )
    subprocess.run(
        [str(python), "-m", "bora_workbench.cli", "calibrate", "--help"],
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


def _export_locked_dependencies(uv: str) -> str:
    """Export exact runtime requirements so verification cannot resolve newer versions."""
    result = subprocess.run(
        [
            uv,
            "export",
            "--frozen",
            "--no-dev",
            "--no-emit-project",
            "--format",
            "requirements-txt",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def _prefetch_locked_dependencies(uv: str, requirements: str) -> None:
    """Populate uv's cache before requiring the isolated installation to work offline."""
    with tempfile.TemporaryDirectory(prefix="bora-workbench-dependencies-") as directory:
        subprocess.run(
            [
                uv,
                "pip",
                "install",
                "--target",
                directory,
                "--require-hashes",
                "--requirements",
                "-",
            ],
            check=True,
            input=requirements,
            text=True,
        )


def _install_locked_wheel(uv: str, python: Path, wheel: Path) -> None:
    """Prefetch exact dependencies, then install dependencies and the wheel offline."""
    requirements = _export_locked_dependencies(uv)
    _prefetch_locked_dependencies(uv, requirements)
    subprocess.run(
        [
            uv,
            "pip",
            "install",
            "--offline",
            "--python",
            str(python),
            "--require-hashes",
            "--requirements",
            "-",
        ],
        check=True,
        input=requirements,
        text=True,
    )
    subprocess.run(
        [uv, "pip", "install", "--offline", "--no-deps", "--python", str(python), str(wheel)],
        check=True,
    )


def _verify_sdist() -> bool:
    """Require one sdist containing installers, current documentation, and evidence."""
    archives = list(Path("dist").glob("*.tar.gz"))
    if len(archives) != 1:
        print(f"expected exactly one sdist in dist/, found {len(archives)}", file=sys.stderr)
        return False
    required = (
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        "IMPLEMENTATION_SPEC.md",
        "docs/README.md",
        "docs/architecture.md",
        "docs/calibration.md",
        "docs/commands.md",
        "docs/configuration.md",
        "docs/development.md",
        "docs/installation.md",
        "docs/operations.md",
        "docs/releasing.md",
        "evidence/README.md",
        "evidence/calibration/windows-11-rtx-2060-super-v3/SHA256SUMS",
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

    with tempfile.TemporaryDirectory(prefix="bora-workbench-wheel-") as directory:
        environment = Path(directory) / "venv"
        subprocess.run([uv, "venv", "--python", "3.12", str(environment)], check=True)
        _install_locked_wheel(uv, environment, wheels[0].resolve())
        python = environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        _verify_install(python, _isolated_environment(Path(directory) / "user-roots"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
