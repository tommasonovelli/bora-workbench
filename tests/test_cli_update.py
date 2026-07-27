"""Test `bora update` presentation, refusals, and exit codes without network or uv.

The command is exercised end to end with the release lookup, the download, and the uv handoff all
replaced, so nothing here reaches GitHub or touches the host installation (section 5.12).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

import bora_workbench._cli_services as service_cli
import bora_workbench._cli_update as update_cli
from bora_workbench.cli import app

runner = CliRunner()


def flat(text: str) -> str:
    """Join a Rich-wrapped stream into one line so a phrase survives any console width.

    Rich wraps at the console width, which differs between a developer terminal and CI, so a
    multi-word phrase can be split across lines without the message having changed.
    """
    return " ".join(text.split())


@pytest.fixture(autouse=True)
def patch_update_dependencies(tmp_path, monkeypatch) -> list[tuple[object, Path]]:
    """Serve one newer release, an idle host, a uv-managed install, and a captured handoff."""
    empty = SimpleNamespace(services=(), warnings=(), stopped=())
    environment = tmp_path / "tools" / "bora-workbench"
    installation = update_cli.ToolInstallation(environment, tmp_path / "uv")
    wheel = tmp_path / "cache" / "updates" / "bora_workbench-9.9.9-py3-none-any.whl"
    wheel.parent.mkdir(parents=True)
    wheel.write_bytes(b"wheel")
    scheduled: list[tuple[object, Path]] = []
    monkeypatch.setattr(service_cli, "service_roots", lambda: (tmp_path / "state",))
    monkeypatch.setattr(service_cli, "status_services", lambda root: empty)
    monkeypatch.setattr(update_cli, "latest_version", lambda: "9.9.9")
    monkeypatch.setattr(update_cli, "inspect_tool_installation", lambda: installation)
    monkeypatch.setattr(update_cli, "cache_dir", lambda: tmp_path / "cache")
    monkeypatch.setattr(update_cli, "download_wheel", lambda _v, _root: wheel)
    monkeypatch.setattr(update_cli, "pinned_engine_release", lambda _w: "b10011")
    monkeypatch.setattr(update_cli, "engine_status", lambda: SimpleNamespace(release="b10011"))
    monkeypatch.setattr(update_cli, "schedule_tool_update", lambda i, w: scheduled.append((i, w)))
    return scheduled


def test_update_installs_the_newer_release_and_reports_the_engine_as_unchanged(
    patch_update_dependencies,
) -> None:
    """Schedule the verified wheel and state that the managed engine stays as it is."""
    result = runner.invoke(app, ["update"])

    assert result.exit_code == 0
    assert "9.9.9" in flat(result.stdout)
    assert "unchanged" in flat(result.stdout)
    assert len(patch_update_dependencies) == 1


def test_update_warns_when_the_new_release_pins_another_engine(
    monkeypatch, patch_update_dependencies
) -> None:
    """Name the required follow-up instead of silently leaving an incompatible engine active."""
    monkeypatch.setattr(update_cli, "pinned_engine_release", lambda _w: "b11000")

    result = runner.invoke(app, ["update"])

    assert result.exit_code == 0
    assert "run `bora engine install` after the update" in flat(result.stdout)
    assert len(patch_update_dependencies) == 1


def test_check_only_reports_without_downloading(monkeypatch, patch_update_dependencies) -> None:
    """Keep `--check` read-only: no download, no uv handoff, exit code 0."""

    def fail(*args, **kwargs) -> Path:
        """Fail the test if the read-only check reaches the download step."""
        raise AssertionError("--check must not download anything")

    monkeypatch.setattr(update_cli, "download_wheel", fail)

    result = runner.invoke(app, ["update", "--check"])

    assert result.exit_code == 0
    assert "9.9.9" in flat(result.stdout)
    assert patch_update_dependencies == []


def test_an_installed_version_at_least_as_new_is_left_alone(
    monkeypatch, patch_update_dependencies
) -> None:
    """Never downgrade or reinstall when no newer release is published."""
    monkeypatch.setattr(update_cli, "latest_version", lambda: "0.0.1")

    result = runner.invoke(app, ["update"])

    assert result.exit_code == 0
    assert "Up to date" in flat(result.stdout)
    assert patch_update_dependencies == []


def test_an_installation_uv_does_not_own_is_refused(
    tmp_path, monkeypatch, patch_update_dependencies
) -> None:
    """Refuse to replace an environment uv cannot manage and point at the installer."""
    foreign = update_cli.ToolInstallation(tmp_path / "checkout" / ".venv", None)
    monkeypatch.setattr(update_cli, "inspect_tool_installation", lambda: foreign)

    result = runner.invoke(app, ["update"])

    assert result.exit_code == 1
    assert "not managed by `uv tool`" in flat(result.stderr)
    assert "Traceback" not in flat(result.stderr)
    assert patch_update_dependencies == []


def test_a_live_managed_service_blocks_the_update(monkeypatch, patch_update_dependencies) -> None:
    """Refuse to replace the launcher of a process that is still holding its environment."""
    live = SimpleNamespace(services=(SimpleNamespace(label="coding"),), warnings=(), stopped=())
    monkeypatch.setattr(service_cli, "status_services", lambda root: live)

    result = runner.invoke(app, ["update"])

    assert result.exit_code == 1
    assert "managed services are running; run bora stop" in flat(result.stderr)
    assert patch_update_dependencies == []


def test_an_unreachable_release_api_exits_one_without_a_traceback(
    monkeypatch, patch_update_dependencies
) -> None:
    """Map a network failure to the operational exit code with an actionable message."""

    def fail() -> str:
        """Simulate an unreachable GitHub release API."""
        raise update_cli.UpdateError("cannot reach the release API: no route to host")

    monkeypatch.setattr(update_cli, "latest_version", fail)

    result = runner.invoke(app, ["update"])

    assert result.exit_code == 1
    assert "Update error" in flat(result.stderr)
    assert "Traceback" not in flat(result.stderr)
    assert patch_update_dependencies == []
