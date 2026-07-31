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
from bora_workbench.process import ProcessError
from bora_workbench.profiles import load_catalog

runner = CliRunner()


def cpu_hardware() -> HardwareInfo:
    """Return deterministic hardware above the default-model launch gate."""
    return HardwareInfo("linux", "test", "Test CPU", 12, 32, 24, "cpu", 0, None, None, None, None)


def patch_preflight(monkeypatch, is_browser_enabled: bool = False) -> list[bool]:
    """Replace external preflight operations while retaining real mode and plan fusion.

    Open WebUI is reported absent unless a test asks for it with `patch_webui`. Without this the
    result would depend on whether the developer running the suite happens to have installed it,
    and a UI mode would try to start a real interface against the real state root.
    """
    requested_vision: list[bool] = []
    monkeypatch.setattr(service_cli, "load_config", lambda: Config(open_browser=is_browser_enabled))
    monkeypatch.setattr(service_cli, "detect_hardware", cpu_hardware)
    patch_webui(monkeypatch, installed=False)

    def resolve(config, lock, request):
        """Record projector demand and return matching synthetic local artifacts."""
        del config, lock
        requested_vision.append(request.require_vision)
        projector = Path("/models/mmproj.gguf") if request.require_vision else None
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


def ready_session(
    mode_id: str, is_browser_enabled: bool, interface: object | None = None
) -> service_cli.PreparedMode:
    """Build one already-ready session for command presentation tests.

    The real dataclass is used rather than a stand-in, so a field added to it has to be considered
    here instead of silently defaulting inside the code under test.
    """
    mode = load_catalog().mode(mode_id)
    assert mode is not None
    plan = SimpleNamespace(
        mode=mode,
        backend="cpu",
        profile_id=None,
        warnings=("fallback warning",),
        alerts=("measured cell needs more free memory",),
    )
    running = SimpleNamespace(state=SimpleNamespace(log_path="server.log"), warnings=())
    ui_url = "http://127.0.0.1:8080/" if interface is None else "http://127.0.0.1:8081"
    return service_cli.PreparedMode(
        running,  # type: ignore[arg-type]
        plan,  # type: ignore[arg-type]
        "http://127.0.0.1:8080/v1",
        ui_url,
        is_browser_enabled,
        interface,  # type: ignore[arg-type]
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
    assert "Interface: the integrated llama.cpp interface." in result.stdout
    assert "fallback warning" in result.stdout
    assert "unavailable: measured cell needs more free memory" in result.stdout
    assert result.stdout.index("fallback warning") < result.stdout.index("unavailable:")
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


def patch_webui(monkeypatch, *, installed: bool, failure: Exception | None = None) -> list[str]:
    """Replace the whole Open WebUI layer with recorders that start no process at all."""
    events: list[str] = []
    status = SimpleNamespace(
        is_installed=installed, root=Path("/managed/open-webui"), executable=Path("open-webui")
    )
    monkeypatch.setattr(service_cli, "inspect_webui", lambda: status)
    monkeypatch.setattr(service_cli, "resolve_secret_key", lambda: "test-key")
    monkeypatch.setattr(service_cli, "launch_environment", lambda launch: {})
    interface = SimpleNamespace(state=SimpleNamespace(log_path="webui.log"), warnings=())

    def start(request):
        """Record the interface start, or fail it the way a real startup failure would."""
        del request
        if failure is not None:
            raise failure
        events.append("interface-ready")
        return interface

    monkeypatch.setattr(service_cli, "start_interface", start)
    monkeypatch.setattr(service_cli, "stop_interface", lambda running: events.append("stopped"))
    return events


def test_open_webui_becomes_the_interface_when_it_is_installed(monkeypatch) -> None:
    """Open the managed interface on its own port once studio finds it installed."""
    patch_preflight(monkeypatch, is_browser_enabled=True)
    patch_webui(monkeypatch, installed=True)
    monkeypatch.setattr(service_cli, "wait_foreground", lambda running: None)
    open_browser = Mock(return_value=True)
    monkeypatch.setattr(service_cli.webbrowser, "open", open_browser)

    result = runner.invoke(app, ["studio", "--force"])

    assert result.exit_code == 0
    assert "Interface: Open WebUI." in result.stdout
    open_browser.assert_called_once_with("http://127.0.0.1:8081", new=2)


def test_the_browser_opens_only_after_both_services_report_ready(monkeypatch) -> None:
    """Open one tab only once the engine and the interface have each answered their own check."""
    patch_preflight(monkeypatch, is_browser_enabled=True)
    events = patch_webui(monkeypatch, installed=True)
    monkeypatch.setattr(service_cli, "wait_foreground", lambda running: None)

    def start_engine(request):
        """Record engine readiness the moment its own start call returns."""
        del request
        events.append("engine-ready")
        return SimpleNamespace(state=SimpleNamespace(log_path="server.log"), warnings=())

    monkeypatch.setattr(service_cli, "start_service", start_engine)
    monkeypatch.setattr(
        service_cli.webbrowser, "open", lambda url, new: events.append("browser") or True
    )

    result = runner.invoke(app, ["studio", "--force"])

    assert result.exit_code == 0
    assert events[:3] == ["engine-ready", "interface-ready", "browser"]


def test_an_absent_open_webui_falls_back_to_the_integrated_interface(monkeypatch) -> None:
    """Keep studio working on a machine that never spent the disk, and say which UI opened."""
    patch_preflight(monkeypatch, is_browser_enabled=True)
    patch_webui(monkeypatch, installed=False)
    monkeypatch.setattr(service_cli, "wait_foreground", lambda running: None)
    open_browser = Mock(return_value=True)
    monkeypatch.setattr(service_cli.webbrowser, "open", open_browser)

    result = runner.invoke(app, ["studio", "--force"])

    assert result.exit_code == 0
    assert "Open WebUI is not installed" in result.stdout
    assert "bora webui install" in result.stdout
    assert "Interface: the integrated llama.cpp interface." in result.stdout
    open_browser.assert_called_once_with("http://127.0.0.1:8080/", new=2)


def test_a_failed_interface_keeps_the_model_serving(monkeypatch) -> None:
    """Never take the engine down with the interface: the reduced fallback is still a UI."""
    patch_preflight(monkeypatch, is_browser_enabled=False)
    patch_webui(monkeypatch, installed=True, failure=ProcessError("exited; inspect webui.log"))
    monkeypatch.setattr(service_cli, "wait_foreground", lambda running: None)

    result = runner.invoke(app, ["studio", "--force"])

    assert result.exit_code == 0
    assert "Open WebUI did not start" in result.stdout
    assert "inspect webui.log" in result.stdout
    assert "UI: http://127.0.0.1:8080/" in result.stdout


def test_the_interface_is_released_when_the_mode_exits(monkeypatch) -> None:
    """Take the interface down on the way out, including after a Ctrl-C in the foreground."""
    patch_preflight(monkeypatch, is_browser_enabled=False)
    events = patch_webui(monkeypatch, installed=True)

    def interrupt(running):
        """Fail the foreground wait the way Ctrl-C does."""
        del running
        raise KeyboardInterrupt

    monkeypatch.setattr(service_cli, "wait_foreground", interrupt)

    result = runner.invoke(app, ["studio", "--force"])

    assert result.exit_code == 130
    assert events == ["interface-ready", "stopped"]


def test_coding_never_starts_an_interface(monkeypatch) -> None:
    """Leave the API-first mode exactly as it was: no second process, no browser, no port."""
    patch_preflight(monkeypatch, is_browser_enabled=True)
    events = patch_webui(monkeypatch, installed=True)
    monkeypatch.setattr(service_cli, "wait_foreground", lambda running: None)
    monkeypatch.setattr(
        service_cli.webbrowser, "open", Mock(side_effect=AssertionError("coding opens no browser"))
    )

    result = runner.invoke(app, ["coding", "--force"])

    assert result.exit_code == 0
    assert events == []


def test_the_preflight_helper_never_consults_the_host_installation(monkeypatch) -> None:
    """Keep every mode test independent of whether this machine has Open WebUI installed.

    Without this the result would flip on a developer who ran `bora webui install`, and a UI mode
    under test would start a real interface and register it in the real state root.
    """
    patch_preflight(monkeypatch)
    monkeypatch.setattr(
        service_cli,
        "start_interface",
        Mock(side_effect=AssertionError("a test must never start a real interface")),
    )

    session = service_cli._prepare_mode("studio", False, Console())

    assert session.interface is None
    assert session.ui_url == "http://127.0.0.1:8080/"
