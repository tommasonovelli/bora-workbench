"""Offline tests for the Step 6A installer scripts (install.sh / install.ps1).

These exercise the host-platform installer with uv replaced by a PATH-shadowing fake, so no
network, package install, real uv, or user configuration is touched. They verify the explicit
single-source contract, the local-wheel SHA-256 gate, and the exact command handed to uv
(IMPLEMENTATION_SPEC.md sections 5.10-5.12 and "Step 6A"). Installer scripts are inherently
platform-specific, so the test selects and runs the script for the host it runs on.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

IS_WINDOWS = os.name == "nt"
REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / ("install.ps1" if IS_WINDOWS else "install.sh")

_FAKE_UV_CMD = """@echo off
if "%~1"=="--version" (echo uv 0.11.28& exit /b 0)
>>"%FAKE_UV_LOG%" echo %*
exit /b 0
"""

_FAKE_UV_SH = """#!/usr/bin/env sh
if [ "$1" = "--version" ]; then
    echo "uv 0.11.28"
    exit 0
fi
printf '%s\\n' "$@" >> "$FAKE_UV_LOG"
exit 0
"""

_WIN_FLAGS = {
    "wheel": "-Wheel",
    "sha256": "-Sha256",
    "git_commit": "-GitCommit",
    "pypi_version": "-PypiVersion",
}
_POSIX_FLAGS = {
    "wheel": "--wheel",
    "sha256": "--sha256",
    "git_commit": "--git-commit",
    "pypi_version": "--pypi-version",
}


@dataclass(frozen=True, slots=True)
class Run:
    """Capture one isolated installer subprocess result and its fake-uv log."""

    returncode: int
    stdout: str
    stderr: str
    log: str


def _write_fake_uv(bin_dir: Path) -> None:
    """Create a PATH-shadowing fake uv that reports 0.11.28 and logs install arguments."""
    bin_dir.mkdir(parents=True, exist_ok=True)
    if IS_WINDOWS:
        # Batch files require CRLF line endings to be parsed reliably by cmd.exe.
        (bin_dir / "uv.cmd").write_bytes(_FAKE_UV_CMD.replace("\n", "\r\n").encode("ascii"))
        return
    fake = bin_dir / "uv"
    fake.write_text(_FAKE_UV_SH, encoding="ascii")
    fake.chmod(0o755)


def _installer_args(**options: str) -> list[str]:
    """Translate logical source options into the host installer's flag names."""
    flags = _WIN_FLAGS if IS_WINDOWS else _POSIX_FLAGS
    args: list[str] = []
    for key, value in options.items():
        args.extend([flags[key], value])
    return args


_POWERSHELL = [
    "powershell.exe",
    "-NoProfile",
    "-NonInteractive",
    "-ExecutionPolicy",
    "Bypass",
]


def _command(args: list[str]) -> list[str]:
    """Build the host command that runs the installer script without a shell."""
    if IS_WINDOWS:
        return [*_POWERSHELL, "-File", str(SCRIPT), *args]
    return ["sh", str(SCRIPT), *args]


def _run(tmp_path: Path, args: list[str]) -> Run:
    """Run the host installer with a fake uv on PATH and the captured uv invocation log."""
    bin_dir = tmp_path / "bin"
    _write_fake_uv(bin_dir)
    log = tmp_path / "uv.log"
    env = dict(os.environ)
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
    env["FAKE_UV_LOG"] = str(log)
    completed = subprocess.run(_command(args), env=env, capture_output=True, text=True)
    log_text = log.read_text(encoding="utf-8") if log.exists() else ""
    return Run(completed.returncode, completed.stdout, completed.stderr, log_text)


def _make_wheel(tmp_path: Path) -> tuple[Path, str]:
    """Write a dummy wheel file and return its path and real SHA-256 digest."""
    wheel = tmp_path / "qwen_launcher-0.1.0-py3-none-any.whl"
    payload = b"not a real wheel; the installer verifies only the digest"
    wheel.write_bytes(payload)
    return wheel, hashlib.sha256(payload).hexdigest()


def test_local_wheel_installs_with_pinned_python(tmp_path: Path) -> None:
    """A verified local wheel is handed to uv with the pinned Python and the wheel path."""
    wheel, digest = _make_wheel(tmp_path)
    result = _run(tmp_path, _installer_args(wheel=str(wheel), sha256=digest))
    assert result.returncode == 0, result.stderr
    normalized_log = " ".join(result.log.splitlines())
    expected = f"tool install --force --python 3.12.13 {wheel}"
    assert expected in normalized_log


def test_local_wheel_bad_hash_refuses_before_install(tmp_path: Path) -> None:
    """A wheel whose digest does not match is rejected before uv is ever invoked."""
    wheel, _ = _make_wheel(tmp_path)
    result = _run(tmp_path, _installer_args(wheel=str(wheel), sha256="0" * 64))
    assert result.returncode == 1
    assert "SHA-256 mismatch" in result.stderr
    assert result.log == ""


def test_wheel_requires_hash(tmp_path: Path) -> None:
    """A wheel source without its SHA-256 is an input error and does not reach uv."""
    wheel, _ = _make_wheel(tmp_path)
    result = _run(tmp_path, _installer_args(wheel=str(wheel)))
    assert result.returncode == 2
    assert result.log == ""


def test_malformed_hash_is_input_error(tmp_path: Path) -> None:
    """A SHA-256 that is not 64 hex characters is rejected as invalid input."""
    wheel, _ = _make_wheel(tmp_path)
    result = _run(tmp_path, _installer_args(wheel=str(wheel), sha256="zz"))
    assert result.returncode == 2


def test_no_source_is_input_error_without_implicit_version(tmp_path: Path) -> None:
    """No source is invalid input because installers never select an implicit version."""
    result = _run(tmp_path, [])
    assert result.returncode == 2
    assert "no version is selected implicitly" in result.stderr
    assert result.log == ""


def test_multiple_sources_rejected(tmp_path: Path) -> None:
    """Two competing sources are invalid input and do not reach uv."""
    result = _run(tmp_path, _installer_args(git_commit="a" * 40, pypi_version="0.1.0"))
    assert result.returncode == 2
    assert result.log == ""


def test_git_commit_source_builds_pinned_reference(tmp_path: Path) -> None:
    """A full commit hash is turned into a pinned git direct reference for uv."""
    commit = "0123456789abcdef0123456789abcdef01234567"
    result = _run(tmp_path, _installer_args(git_commit=commit))
    assert result.returncode == 0, result.stderr
    assert f"git+https://github.com/tommasonovelli/qwen-launcher.git@{commit}" in result.log


def test_git_commit_must_be_full_hash(tmp_path: Path) -> None:
    """A short or non-hex commit is rejected as invalid input."""
    result = _run(tmp_path, _installer_args(git_commit="abc123"))
    assert result.returncode == 2


def test_pypi_version_source_pins_exact_version(tmp_path: Path) -> None:
    """An explicit PyPI version is pinned exactly in the uv install target."""
    result = _run(tmp_path, _installer_args(pypi_version="0.1.0"))
    assert result.returncode == 0, result.stderr
    assert "qwen-launcher==0.1.0" in result.log


def test_windows_checksum_does_not_require_get_file_hash() -> None:
    """Keep hashing independent of module discovery across PowerShell 7 and Windows PowerShell."""
    script = (REPO_ROOT / "install.ps1").read_text(encoding="utf-8")

    assert "Get-FileHash" not in script
    assert "[System.Security.Cryptography.SHA256]::Create()" in script
