"""Tests for the `bora webui` commands and for keeping the session key out of every output."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

import bora_workbench._cli_diagnostics as diagnostics_cli
import bora_workbench._cli_services as service_cli
import bora_workbench._cli_webui as webui_cli
import bora_workbench.snapshot as snapshot_module
from bora_workbench.cli import app
from bora_workbench.webui import OPEN_WEBUI_VERSION, WebuiError, launch_environment
from bora_workbench.webui import WebuiLaunch as Launch
from tests.test_cli_update import flat

runner = CliRunner()


def _status(installed: bool, root: Path = Path("/managed/open-webui")) -> SimpleNamespace:
    """Return one inspection result without touching the filesystem."""
    return SimpleNamespace(is_installed=installed, root=root, executable=None)


def test_status_reports_an_absent_installation_and_the_remedy(monkeypatch) -> None:
    """Tell a user who never installed it exactly which command changes that."""
    monkeypatch.setattr(webui_cli, "inspect_webui", lambda: _status(False))

    result = runner.invoke(app, ["webui", "status"])

    assert result.exit_code == 0
    assert "not installed" in result.stdout
    assert "bora webui install" in result.stdout
    assert "8081" in result.stdout


def test_status_reports_the_pinned_version_when_present(monkeypatch) -> None:
    """Name the exact release, so two machines can be compared without guessing."""
    monkeypatch.setattr(webui_cli, "inspect_webui", lambda: _status(True))

    result = runner.invoke(app, ["webui", "status"])

    assert result.exit_code == 0
    assert OPEN_WEBUI_VERSION in result.stdout


def test_the_session_key_reaches_no_command_output(monkeypatch) -> None:
    """Keep the first secret this project stores out of status, doctor, and every diagnostic."""
    secret = "do-not-print-this-key"
    monkeypatch.setattr(webui_cli, "inspect_webui", lambda: _status(True))
    monkeypatch.setattr(service_cli, "resolve_secret_key", lambda: secret)

    status = runner.invoke(app, ["webui", "status"])
    doctor = runner.invoke(app, ["doctor"])

    assert secret not in status.stdout
    assert secret not in doctor.stdout
    assert "WEBUI_SECRET_KEY" not in doctor.stdout


def test_the_environment_holds_the_key_that_no_output_shows() -> None:
    """Prove the key is passed where it is needed, which is what makes its absence meaningful."""
    launch = Launch(Path("open-webui"), 8081, 8080, Path("/data"), "a-secret")

    assert launch_environment(launch)["WEBUI_SECRET_KEY"] == "a-secret"


def test_install_refuses_while_a_managed_service_is_running(monkeypatch) -> None:
    """Never replace an environment a live interface still has open."""
    live = SimpleNamespace(services=(SimpleNamespace(pid=1),), warnings=(), stopped=())
    monkeypatch.setattr(service_cli, "service_roots", lambda: (Path("state"),))
    monkeypatch.setattr(service_cli, "status_services", lambda root: live)
    monkeypatch.setattr(
        webui_cli, "install_webui", lambda **kwargs: _forbidden("install must not run")
    )

    result = runner.invoke(app, ["webui", "install"])

    assert result.exit_code == 1
    assert "run bora stop" in flat(result.stderr)


def _forbidden(message: str) -> None:
    """Raise inside a lambda so a forbidden call fails the test where it happens."""
    raise AssertionError(message)


def _no_services(monkeypatch) -> None:
    """Report an idle machine so an installation is allowed to proceed."""
    empty = SimpleNamespace(services=(), warnings=(), stopped=())
    monkeypatch.setattr(service_cli, "service_roots", lambda: (Path("state"),))
    monkeypatch.setattr(service_cli, "status_services", lambda root: empty)


def test_install_states_the_cost_and_whose_program_it_is(monkeypatch) -> None:
    """Say what the command spends and what it starts, before it spends it."""
    _no_services(monkeypatch)
    monkeypatch.setattr(webui_cli, "inspect_webui", lambda: _status(False))
    monkeypatch.setattr(webui_cli, "install_webui", lambda **kwargs: _status(True))

    result = runner.invoke(app, ["webui", "install"])

    assert result.exit_code == 0
    assert "gigabytes" in result.stdout
    assert "separate program" in result.stdout
    assert OPEN_WEBUI_VERSION in result.stdout


def test_install_maps_a_failure_to_exit_one_without_a_traceback(monkeypatch) -> None:
    """Report an actionable installation failure the way every other command does."""
    _no_services(monkeypatch)
    monkeypatch.setattr(webui_cli, "inspect_webui", lambda: _status(False))

    def fail(**kwargs):
        """Fail the installation the way a missing prerequisite would."""
        del kwargs
        raise WebuiError("uv is required to install Open WebUI")

    monkeypatch.setattr(webui_cli, "install_webui", fail)

    result = runner.invoke(app, ["webui", "install"])

    assert result.exit_code == 1
    assert "uv is required" in flat(result.stderr)
    assert "Traceback" not in result.stderr


def test_doctor_names_the_interface_state_and_its_port(monkeypatch) -> None:
    """Show on one line whether studio will open Open WebUI or the built-in interface."""
    monkeypatch.setattr(snapshot_module, "inspect_webui", lambda: _status(False))

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert "not installed; studio opens the integrated interface" in flat(result.stdout)
    assert "8081" in result.stdout


def test_engine_install_acquires_the_interface_by_default(monkeypatch) -> None:
    """Put the interface where a first setup already spends gigabytes and waits."""
    acquired: list[bool] = []
    monkeypatch.setattr(
        diagnostics_cli, "install_managed_webui", lambda force, stdout: acquired.append(force)
    )
    _stub_engine(monkeypatch)

    result = runner.invoke(app, ["engine", "install", "--no-model"])

    assert result.exit_code == 0
    assert acquired == [False]


def test_no_webui_declines_the_interface_without_removing_anything(monkeypatch) -> None:
    """Leave a machine that only wants the API free of a six-gigabyte closure."""
    monkeypatch.setattr(
        diagnostics_cli,
        "install_managed_webui",
        lambda force, stdout: _forbidden("--no-webui must acquire nothing"),
    )
    _stub_engine(monkeypatch)

    result = runner.invoke(app, ["engine", "install", "--no-model", "--no-webui"])

    assert result.exit_code == 0


def _stub_engine(monkeypatch) -> None:
    """Replace engine acquisition so no build, download, or hardware probe happens."""
    hardware = SimpleNamespace(backend="cpu", warnings=())
    status = SimpleNamespace(
        is_active=True, release="b10011", backend="cpu", executable=Path("server"), differences=()
    )
    monkeypatch.setattr(diagnostics_cli, "detect_hardware", lambda: hardware)
    monkeypatch.setattr(
        diagnostics_cli,
        "_install_with_progress",
        lambda backend, force, stdout: SimpleNamespace(status=status, is_installed=True),
    )
    monkeypatch.setattr(diagnostics_cli, "_report_install", lambda result, stdout: None)


def test_remove_frees_the_environment_and_asks_about_chats_separately(monkeypatch) -> None:
    """Ask two questions, because reinstallable bytes and a user's own content differ."""
    removed: list[str] = []
    root = Path("/managed/open-webui")
    monkeypatch.setattr(webui_cli, "inspect_webui", lambda: _status(True, root))
    monkeypatch.setattr(webui_cli, "directory_size", lambda path: 1024)
    monkeypatch.setattr(Path, "is_dir", lambda self: True)
    monkeypatch.setattr(webui_cli, "remove_environment", lambda: removed.append("environment"))
    monkeypatch.setattr(webui_cli, "remove_interface_data", lambda: removed.append("data"))
    _no_services(monkeypatch)

    result = runner.invoke(app, ["webui", "remove"], input="y\nn\n")

    assert result.exit_code == 0
    assert "Remove the managed Open WebUI environment?" in result.stdout
    assert "Also remove the interface data?" in result.stdout
    assert "chats, notes, uploads" in result.stdout
    assert removed == ["environment"]


def test_declining_both_questions_removes_nothing(monkeypatch) -> None:
    """Keep a default of no on both questions, so an accidental Enter deletes nothing."""
    monkeypatch.setattr(webui_cli, "inspect_webui", lambda: _status(True))
    monkeypatch.setattr(webui_cli, "directory_size", lambda path: 1024)
    monkeypatch.setattr(Path, "is_dir", lambda self: True)
    monkeypatch.setattr(
        webui_cli, "remove_environment", lambda: _forbidden("nothing may be removed")
    )
    monkeypatch.setattr(
        webui_cli, "remove_interface_data", lambda: _forbidden("nothing may be removed")
    )
    _no_services(monkeypatch)

    result = runner.invoke(app, ["webui", "remove"], input="\n\n")

    assert result.exit_code == 0
    assert "Environment kept." in result.stdout
    assert "Interface data kept" in result.stdout


def test_remove_refuses_while_a_managed_service_is_running(monkeypatch) -> None:
    """Never delete an environment a live interface still has open."""
    live = SimpleNamespace(services=(SimpleNamespace(pid=1),), warnings=(), stopped=())
    monkeypatch.setattr(service_cli, "service_roots", lambda: (Path("state"),))
    monkeypatch.setattr(service_cli, "status_services", lambda root: live)

    result = runner.invoke(app, ["webui", "remove"])

    assert result.exit_code == 1
    assert "run bora stop" in flat(result.stderr)


def test_uninstall_names_the_interface_content_it_deletes(monkeypatch) -> None:
    """Say that a full uninstall takes the chats with it, since nothing asks about them."""
    _no_services(monkeypatch)
    monkeypatch.setattr(
        service_cli,
        "inspect_tool_installation",
        lambda: SimpleNamespace(is_managed_by_uv=False, environment=Path("tool")),
    )

    result = runner.invoke(app, ["uninstall"], input="n\n")

    assert "Open WebUI" in flat(result.stdout)
    assert "bora webui remove" in flat(result.stdout)
