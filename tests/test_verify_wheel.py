"""Tests for deterministic wheel verification with an offline installation phase."""

from pathlib import Path
from types import SimpleNamespace

from scripts import verify_wheel


def test_install_prefetches_locked_dependencies_before_offline_verification(
    tmp_path, monkeypatch
) -> None:
    """Populate a fresh CI cache, then install exact dependencies and the wheel offline."""
    calls: list[tuple[list[str], dict[str, object]]] = []

    def run(command, **kwargs):
        """Capture subprocess contracts and return one synthetic lock export."""
        calls.append((command, kwargs))
        return SimpleNamespace(stdout="httpx==0.28.1 --hash=sha256:deadbeef\n")

    monkeypatch.setattr(verify_wheel.subprocess, "run", run)
    python = tmp_path / "python"
    wheel = Path("dist/bora_workbench-0.2.1-py3-none-any.whl")
    requirements = "httpx==0.28.1 --hash=sha256:deadbeef\n"

    verify_wheel._install_locked_wheel("uv", python, wheel)

    assert calls[0][0][:3] == ["uv", "export", "--frozen"]
    assert calls[0][0][3:] == ["--no-dev", "--no-emit-project", "--format", "requirements-txt"]
    assert calls[1][0][:4] == ["uv", "pip", "install", "--target"]
    assert calls[1][1]["input"] == requirements
    assert calls[2][0][:6] == ["uv", "pip", "install", "--offline", "--python", str(python)]
    assert calls[2][0][6:] == ["--require-hashes", "--requirements", "-"]
    assert calls[2][1]["input"] == requirements
    assert calls[3][0][3:5] == ["--offline", "--no-deps"]
