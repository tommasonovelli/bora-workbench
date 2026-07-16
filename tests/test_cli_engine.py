"""CLI tests for managed-engine installation and compatibility status."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

import qwen_launcher._cli_engine as engine_cli
from qwen_launcher._engine_types import EngineStatus, InstallResult
from qwen_launcher.cli import app

runner = CliRunner()


def test_engine_install_uses_detected_backend_and_reports_activation(monkeypatch) -> None:
    """Select the detected backend and present the promoted executable."""
    monkeypatch.setattr(
        engine_cli,
        "detect_hardware",
        lambda: SimpleNamespace(backend="cuda", warnings=()),
    )
    status = EngineStatus(True, "b10011", "cuda", Path("llama-server.exe"), True)
    monkeypatch.setattr(
        engine_cli,
        "install_engine",
        lambda backend, force: InstallResult(status, True),
    )

    result = runner.invoke(app, ["engine", "install"])

    assert result.exit_code == 0
    assert "backend=cuda" in result.stdout
    assert "Installed and activated" in result.stdout
    assert "NVIDIA CUDA EULA" in result.stdout


def test_engine_status_is_zero_when_absent(monkeypatch) -> None:
    """Treat an absent managed installation as readable status rather than an operation failure."""
    absent = EngineStatus(False, None, None, None, False, ("not installed",))
    monkeypatch.setattr(engine_cli, "engine_status", lambda: absent)

    result = runner.invoke(app, ["engine", "status"])

    assert result.exit_code == 0
    assert "not installed" in result.stdout


def test_engine_status_returns_one_for_corrupt_manifest(monkeypatch) -> None:
    """Expose manifest corruption and use the expected operational failure exit code."""
    corrupt = EngineStatus(False, None, None, None, False, ("manifest is invalid",))
    monkeypatch.setattr(engine_cli, "engine_status", lambda: corrupt)

    result = runner.invoke(app, ["engine", "status"])

    assert result.exit_code == 1
    assert "manifest is invalid" in result.stdout
