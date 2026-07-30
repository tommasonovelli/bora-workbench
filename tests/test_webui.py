"""Tests for the managed Open WebUI installation, environment, and readiness contract.

Nothing here installs, downloads, or starts anything: `uv` is replaced by a recorder, so the tests
assert on the commands and the environment bora would produce rather than on a real interface.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

import bora_workbench.webui as webui_module
from bora_workbench.webui import (
    OPEN_WEBUI_VERSION,
    WebuiError,
    WebuiLaunch,
    inspect_webui,
    install_webui,
    launch_environment,
    readiness_contract,
    resolve_secret_key,
    serve_command,
)


def _launch(port: int = 8081, llama_port: int = 8080) -> WebuiLaunch:
    """Build one resolved launch without touching the filesystem."""
    return WebuiLaunch(Path("/managed/open-webui"), port, llama_port, Path("/data"), "test-key")


def _install_environment(root: Path, *, version: str = OPEN_WEBUI_VERSION) -> Path:
    """Create the exact shape a completed installation leaves behind."""
    environment = root / "venv"
    scripts = environment / ("Scripts" if os.name == "nt" else "bin")
    scripts.mkdir(parents=True)
    executable = scripts / ("open-webui.exe" if os.name == "nt" else "open-webui")
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    (environment / "installed.json").write_text(
        json.dumps({"version": version, "python": "3.12"}), encoding="utf-8"
    )
    return executable


def test_serve_command_always_binds_loopback(tmp_path) -> None:
    """Refuse upstream's `0.0.0.0` default on every path by never reading a host from anywhere."""
    command = serve_command(_launch(port=9090))

    assert command[1:] == ("serve", "--host", "127.0.0.1", "--port", "9090")
    assert "0.0.0.0" not in command


def test_readiness_polls_ready_and_not_health() -> None:
    """Poll the endpoint that waits for startup, not the one that answers before it."""
    contract = readiness_contract(8081)

    assert contract.url == "http://127.0.0.1:8081/ready"
    assert contract.ready_status == 200
    assert contract.ready_body == {"status": True}
    assert contract.transient_statuses == (503,)


def test_environment_never_sets_a_name_even_when_one_is_inherited(monkeypatch) -> None:
    """Keep the interface named `Open WebUI`, so its branding clause is never engaged."""
    monkeypatch.setenv("WEBUI_NAME", "something-else")

    environment = launch_environment(_launch())

    assert "WEBUI_NAME" not in environment


def test_environment_carries_every_settled_value() -> None:
    """Assemble the whole configuration in one place, including each switch with a reason."""
    environment = launch_environment(_launch(port=8081, llama_port=8080))

    assert environment["DATA_DIR"] == str(Path("/data"))
    assert environment["WEBUI_AUTH"] == "false"
    assert environment["WEBUI_URL"] == "http://127.0.0.1:8081"
    assert environment["ENABLE_PERSISTENT_CONFIG"] == "true"
    assert environment["OPENAI_API_BASE_URL"] == "http://127.0.0.1:8080/v1"
    assert environment["ENABLE_OLLAMA_API"] == "false"
    assert environment["ENABLE_VERSION_UPDATE_CHECK"] == "false"
    assert environment["RAG_EMBEDDING_MODEL"] == ""
    assert environment["RAG_EMBEDDING_ENGINE"]


def test_no_third_party_python_can_run_inside_the_managed_process() -> None:
    """Set both switches, because an installation is immutable or it is not."""
    environment = launch_environment(_launch())

    assert environment["ENABLE_PIP_INSTALL_FRONTMATTER_REQUIREMENTS"] == "false"
    assert environment["SAFE_MODE"] == "true"


def test_the_three_extra_completions_per_turn_are_disabled() -> None:
    """Keep the single calibrated slot for the stream the user is actually waiting on."""
    environment = launch_environment(_launch())

    assert environment["ENABLE_TITLE_GENERATION"] == "false"
    assert environment["ENABLE_TAGS_GENERATION"] == "false"
    assert environment["ENABLE_FOLLOW_UP_GENERATION"] == "false"


def test_secret_key_is_created_once_and_reused(tmp_path) -> None:
    """Reuse one stable key, or the browser is logged out at every launch."""
    first = resolve_secret_key(tmp_path)
    second = resolve_secret_key(tmp_path)

    assert first == second
    assert first


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits do not apply on Windows")
def test_secret_key_is_readable_only_by_its_owner(tmp_path) -> None:
    """Keep the first secret this project stores out of reach of other local accounts."""
    resolve_secret_key(tmp_path)

    mode = (tmp_path / "open-webui.secret").stat().st_mode
    assert stat.S_IMODE(mode) == 0o600


def test_an_empty_secret_key_is_an_error_rather_than_a_silent_regeneration(tmp_path) -> None:
    """Refuse to launch on a truncated key instead of invalidating every existing session."""
    (tmp_path / "open-webui.secret").write_text("", encoding="ascii")

    with pytest.raises(WebuiError, match="is empty"):
        resolve_secret_key(tmp_path)


def test_absent_installation_is_reported_as_not_installed(tmp_path) -> None:
    """Report a machine that never ran the install without creating anything on it."""
    status = inspect_webui(tmp_path / "open-webui")

    assert not status.is_installed
    assert status.version is None
    assert not (tmp_path / "open-webui").exists()


def test_a_different_recorded_version_is_not_the_pinned_one(tmp_path) -> None:
    """Treat an environment left by another release as absent rather than as usable."""
    _install_environment(tmp_path, version="0.10.0")

    assert not inspect_webui(tmp_path).is_installed


def test_a_complete_installation_is_reported_with_its_executable(tmp_path) -> None:
    """Require both the recorded version and a real console script before claiming installed."""
    executable = _install_environment(tmp_path)

    status = inspect_webui(tmp_path)

    assert status.is_installed
    assert status.version == OPEN_WEBUI_VERSION
    assert status.executable == executable


def _record_uv(monkeypatch, tmp_path, *, fail_at: int | None = None) -> list[list[str]]:
    """Replace uv with a recorder that creates the console script the installer verifies."""
    commands: list[list[str]] = []

    class _Result:
        """Stand in for a completed process with only the field the installer reads."""

        def __init__(self, returncode: int) -> None:
            """Retain only the exit status the installer inspects."""
            self.returncode = returncode

    def run(command, check):
        """Record one installer step and simulate its filesystem effect."""
        del check
        commands.append(list(command))
        if fail_at is not None and len(commands) == fail_at:
            return _Result(1)
        if command[1] == "pip":
            _install_environment(tmp_path)
        return _Result(0)

    monkeypatch.setattr(webui_module.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(webui_module.subprocess, "run", run)
    return commands


def test_install_creates_the_environment_and_pins_the_exact_version(tmp_path, monkeypatch) -> None:
    """Install one pinned release, never a resolved range, into a managed environment."""
    commands = _record_uv(monkeypatch, tmp_path)

    status = install_webui(tmp_path)

    assert status.is_installed
    assert commands[0][:4] == ["/usr/bin/uv", "venv", "--python", "3.12"]
    assert commands[1][:3] == ["/usr/bin/uv", "pip", "install"]
    assert f"open-webui=={OPEN_WEBUI_VERSION}" in commands[1]
    assert "latest" not in " ".join(commands[1])


def test_an_interrupted_install_leaves_nothing_that_reports_as_installed(
    tmp_path, monkeypatch
) -> None:
    """Write the version marker last, so a failed step cannot be mistaken for a usable one."""
    _record_uv(monkeypatch, tmp_path, fail_at=2)

    with pytest.raises(WebuiError, match="install"):
        install_webui(tmp_path)

    assert not inspect_webui(tmp_path).is_installed


def test_install_is_idempotent_and_runs_nothing_when_already_pinned(tmp_path, monkeypatch) -> None:
    """Skip a multi-gigabyte reinstall when the pinned version is already present."""
    _install_environment(tmp_path)
    commands = _record_uv(monkeypatch, tmp_path)

    status = install_webui(tmp_path)

    assert status.is_installed
    assert commands == []


def test_install_without_uv_names_the_missing_tool(tmp_path, monkeypatch) -> None:
    """Report the one prerequisite by name instead of failing inside a subprocess call."""
    monkeypatch.setattr(webui_module.shutil, "which", lambda name: None)

    with pytest.raises(WebuiError, match="uv is required"):
        install_webui(tmp_path)
