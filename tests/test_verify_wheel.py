"""Tests for deterministic, offline wheel verification."""

from pathlib import Path
from types import SimpleNamespace

from scripts import verify_wheel


def test_install_uses_frozen_locked_dependencies_offline(tmp_path, monkeypatch) -> None:
    """Install exact lock exports before the wheel without resolving newer dependencies."""
    calls: list[tuple[list[str], dict[str, object]]] = []

    def run(command, **kwargs):
        """Capture subprocess contracts and return one synthetic lock export."""
        calls.append((command, kwargs))
        return SimpleNamespace(stdout="httpx==0.28.1 --hash=sha256:deadbeef\n")

    monkeypatch.setattr(verify_wheel.subprocess, "run", run)
    python = tmp_path / "python"
    wheel = Path("dist/bora_workbench-0.2.0-py3-none-any.whl")

    verify_wheel._install_locked_wheel("uv", python, wheel)

    assert calls[0][0] == [
        "uv",
        "export",
        "--frozen",
        "--no-dev",
        "--no-emit-project",
        "--format",
        "requirements-txt",
    ]
    assert calls[1][0] == [
        "uv",
        "pip",
        "install",
        "--offline",
        "--python",
        str(python),
        "--require-hashes",
        "--requirements",
        "-",
    ]
    assert calls[1][1]["input"] == "httpx==0.28.1 --hash=sha256:deadbeef\n"
    assert calls[2][0][3:5] == ["--offline", "--no-deps"]
