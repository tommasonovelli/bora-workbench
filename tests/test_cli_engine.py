"""CLI tests for managed-engine installation and compatibility status."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

import bora_workbench._cli_diagnostics as diagnostics_cli
from bora_workbench.cli import app
from bora_workbench.engine import EngineError, EngineStatus, InstallProgressEvent, InstallResult

runner = CliRunner()


def test_engine_install_uses_detected_backend_and_reports_activation(monkeypatch) -> None:
    """Select the detected backend and present the promoted executable."""
    monkeypatch.setattr(
        diagnostics_cli,
        "detect_hardware",
        lambda: SimpleNamespace(backend="cuda", warnings=()),
    )
    status = EngineStatus(True, "b10011", "cuda", Path("llama-server.exe"), True)

    def install(backend, force, progress):
        """Report the long-running phase before returning a successful fake install."""
        del backend, force
        progress(InstallProgressEvent("compile"))
        return InstallResult(status, True)

    monkeypatch.setattr(diagnostics_cli, "install_engine", install)

    result = runner.invoke(app, ["engine", "install", "--no-model"])

    assert result.exit_code == 0
    assert "backend=cuda" in result.stdout
    assert "Configuring and compiling Ubuntu CUDA" in result.stdout
    assert "Installed and activated" in result.stdout
    assert "NVIDIA CUDA EULA" in result.stdout


def test_engine_status_is_zero_when_absent(monkeypatch) -> None:
    """Treat an absent managed installation as readable status rather than an operation failure."""
    absent = EngineStatus(False, None, None, None, False, ("not installed",))
    monkeypatch.setattr(diagnostics_cli, "engine_status", lambda: absent)

    result = runner.invoke(app, ["engine", "status"])

    assert result.exit_code == 0
    assert "not installed" in result.stdout


def test_engine_status_keeps_every_blocking_difference_on_stderr(monkeypatch) -> None:
    """Keep a redirected blocking difference list complete on one error stream."""
    differences = ("manifest is invalid", "active release does not match engine.lock")
    corrupt = EngineStatus(False, None, None, None, False, differences)
    monkeypatch.setattr(diagnostics_cli, "engine_status", lambda: corrupt)

    result = runner.invoke(app, ["engine", "status"])

    assert result.exit_code == 1
    for difference in differences:
        assert difference in result.stderr
        assert difference not in result.stdout
    assert "Traceback" not in result.stderr


def test_engine_status_maps_inspection_error_without_traceback(monkeypatch) -> None:
    """Map a lock or manifest read failure onto stderr and the operational exit code."""
    error = EngineError("cannot read active manifest")
    monkeypatch.setattr(
        diagnostics_cli,
        "engine_status",
        lambda: (_ for _ in ()).throw(error),
    )

    result = runner.invoke(app, ["engine", "status"])

    assert result.exit_code == 1
    assert "cannot read active manifest" in result.stderr
    assert "Traceback" not in result.stderr
