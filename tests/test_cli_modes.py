"""Tests for studio and vstudio preparation, presentation, and browser behavior."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from rich.console import Console
from typer.testing import CliRunner

import bora_workbench._cli_services as service_cli
from bora_workbench.cli import app
from bora_workbench.config import Config
from bora_workbench.engine import ResolvedModel
from bora_workbench.hardware import HardwareInfo
from bora_workbench.profiles import load_catalog

runner = CliRunner()


def cpu_hardware() -> HardwareInfo:
    """Return deterministic hardware above the default-model launch gate."""
    return HardwareInfo("linux", "test", "Test CPU", 12, 32, 24, "cpu", 0, None, None, None, None)


def patch_preflight(monkeypatch, is_browser_enabled: bool = False) -> list[bool]:
    """Replace external preflight operations while retaining real mode and plan fusion."""
    requested_vision: list[bool] = []
    monkeypatch.setattr(service_cli, "load_config", lambda: Config(open_browser=is_browser_enabled))
    monkeypatch.setattr(service_cli, "detect_hardware", cpu_hardware)

    def resolve(config, lock, require_vision=False):
        """Record projector demand and return matching synthetic local artifacts."""
        del config, lock
        requested_vision.append(require_vision)
        projector = Path("/models/mmproj.gguf") if require_vision else None
        return ResolvedModel(Path("/models/model.gguf"), projector)

    monkeypatch.setattr(service_cli, "resolve_model", resolve)
    monkeypatch.setattr(service_cli, "locate", lambda config, backend, lock: Path("server"))
    monkeypatch.setattr(service_cli, "build_command", lambda executable, plan, lock: ("server",))
    running = SimpleNamespace(state=SimpleNamespace(log_path="server.log"), warnings=())
    monkeypatch.setattr(service_cli, "start_service", lambda request: running)
    return requested_vision


@pytest.mark.parametrize(("mode_id", "requires_vision"), [("studio", False), ("vstudio", True)])
def test_prepares_ui_modes_with_only_the_required_projector(
    mode_id, requires_vision, monkeypatch
) -> None:
    """Resolve mmproj only for vstudio and retain the lock-derived local endpoints."""
    requested_vision = patch_preflight(monkeypatch)

    session = service_cli._prepare_mode(mode_id, False, Console())

    assert requested_vision == [requires_vision]
    assert session.plan.mode.id == mode_id
    assert session.plan.mode.services.ui is True
    assert (session.plan.mmproj_path is not None) is requires_vision
    assert session.api_url == "http://127.0.0.1:8080/v1"
    assert session.ui_url == "http://127.0.0.1:8080/"


def ready_session(mode_id: str, is_browser_enabled: bool) -> SimpleNamespace:
    """Build one already-ready session for command presentation tests."""
    mode = load_catalog().mode(mode_id)
    assert mode is not None
    plan = SimpleNamespace(
        mode=mode,
        backend="cpu",
        profile_id=None,
        warnings=("fallback warning",),
    )
    running = SimpleNamespace(state=SimpleNamespace(log_path="server.log"), warnings=())
    return SimpleNamespace(
        running=running,
        plan=plan,
        api_url="http://127.0.0.1:8080/v1",
        ui_url="http://127.0.0.1:8080/",
        is_browser_enabled=is_browser_enabled,
    )


@pytest.mark.parametrize("mode_id", ["studio", "vstudio"])
def test_ui_commands_open_browser_after_ready(mode_id, monkeypatch) -> None:
    """Show both endpoints and open the integrated UI for each configured UI mode."""
    session = ready_session(mode_id, True)
    monkeypatch.setattr(service_cli, "_prepare_mode", lambda *args: session)
    monkeypatch.setattr(service_cli, "wait_foreground", lambda running: None)
    open_browser = Mock(return_value=True)
    monkeypatch.setattr(service_cli.webbrowser, "open", open_browser)

    result = runner.invoke(app, [mode_id, "--force"])

    assert result.exit_code == 0
    assert f"mode={mode_id}" in result.stdout
    assert "API endpoint: http://127.0.0.1:8080/v1" in result.stdout
    assert "UI: http://127.0.0.1:8080/" in result.stdout
    assert "essential integrated llama.cpp UI" in result.stdout
    assert "fallback warning" in result.stdout
    open_browser.assert_called_once_with("http://127.0.0.1:8080/", new=2)


def test_browser_disabled_never_attempts_to_open(monkeypatch) -> None:
    """Honor open_browser=false while still displaying the manually usable UI URL."""
    monkeypatch.setattr(service_cli, "_prepare_mode", lambda *args: ready_session("studio", False))
    monkeypatch.setattr(service_cli, "wait_foreground", lambda running: None)
    open_browser = Mock(side_effect=AssertionError("browser must remain disabled"))
    monkeypatch.setattr(service_cli.webbrowser, "open", open_browser)

    result = runner.invoke(app, ["studio"])

    assert result.exit_code == 0
    assert "UI: http://127.0.0.1:8080/" in result.stdout
    open_browser.assert_not_called()
