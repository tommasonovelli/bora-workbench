"""Test exact uv tool identification and helper error mapping without host removal.

Nothing here removes a real installation: uv is never executed, and the detached helper module is
only exercised through its own error mapping. `_tool_helper` deliberately stays a separate module
because `_tool_handoff.schedule_uv_command` spawns it with `python -m`, so it must remain importable
after the tool environment it was started from has been deleted or replaced.
"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import bora_workbench._tool_handoff as handoff
import bora_workbench._tool_helper as helper
import bora_workbench.uninstall as uninstall


def _tool_environment(tmp_path: Path) -> Path:
    """Create the minimum uv receipt required to identify one managed tool environment."""
    environment = tmp_path / "tools" / "bora-workbench"
    environment.mkdir(parents=True)
    (environment / "uv-receipt.toml").write_text("[tool]\n", encoding="utf-8")
    return environment


def test_inspection_accepts_only_the_current_received_uv_environment(tmp_path, monkeypatch) -> None:
    """Treat an exact prefix and receipt under uv's configured root as self-removable."""
    environment = _tool_environment(tmp_path)
    uv_executable = tmp_path / "bin" / "uv"
    monkeypatch.setattr(handoff.sys, "prefix", str(environment))
    monkeypatch.setattr(handoff.shutil, "which", lambda _name: str(uv_executable))
    monkeypatch.setattr(handoff, "_query_tool_root", lambda _uv: tmp_path / "tools")

    installation = handoff.inspect_tool_installation()

    assert installation.environment == environment.resolve()
    assert installation.uv_executable == uv_executable.resolve()
    assert installation.is_managed_by_uv


def test_inspection_rejects_a_different_python_environment(tmp_path, monkeypatch) -> None:
    """Never remove a global uv tool merely because uninstall ran from a checkout or other venv."""
    _tool_environment(tmp_path)
    monkeypatch.setattr(handoff.sys, "prefix", str(tmp_path / "checkout" / ".venv"))
    monkeypatch.setattr(handoff.shutil, "which", lambda _name: str(tmp_path / "uv"))
    monkeypatch.setattr(handoff, "_query_tool_root", lambda _uv: tmp_path / "tools")

    installation = handoff.inspect_tool_installation()

    assert not installation.is_managed_by_uv


def test_uv_tool_directory_failure_is_actionable(monkeypatch) -> None:
    """Expose uv inspection stderr instead of guessing a tool root or deleting anything."""
    failed = SimpleNamespace(returncode=2, stdout="", stderr="invalid uv config")
    monkeypatch.setattr(handoff.subprocess, "run", lambda *args, **kwargs: failed)

    with pytest.raises(handoff.ToolHandoffError, match="invalid uv config"):
        handoff._query_tool_root(Path("uv"))


def test_handoff_token_accepts_fragmented_socket_reads() -> None:
    """Reassemble a stream token because one recv call is not guaranteed to return every byte."""
    channel = SimpleNamespace(recv=Mock(side_effect=[b"ab", b"c", b"def"]))

    assert handoff._receive_token(channel, 6) == b"abcdef"


def test_an_installation_uv_does_not_own_schedules_nothing(monkeypatch) -> None:
    """Leave a non-uv installation untouched instead of spawning a helper against it."""
    started: list[object] = []
    monkeypatch.setattr(handoff, "_start_helper", lambda *args: started.append(args))

    handoff.schedule_uv_command(handoff.ToolInstallation(Path("env"), None), ("tool", "dir"))

    assert started == []


def test_tool_removal_hands_uv_the_exact_uninstall_command(monkeypatch) -> None:
    """Keep removal targeting this distribution only, never another uv tool."""
    scheduled: list[tuple[str, ...]] = []
    monkeypatch.setattr(uninstall, "schedule_uv_command", lambda _i, args: scheduled.append(args))

    uninstall.schedule_tool_removal(uninstall.ToolInstallation(Path("env"), Path("uv")))

    assert scheduled == [("tool", "uninstall", "bora-workbench")]


def test_helper_reports_uv_failure(monkeypatch, capsys) -> None:
    """Keep a deferred uv failure visible even though the original command already exited."""
    failed = SimpleNamespace(returncode=7)
    monkeypatch.setattr(helper.subprocess, "run", lambda *args, **kwargs: failed)

    assert helper._run_uv("uv", ["tool", "uninstall", "bora-workbench"]) == 7
    assert "exited with code 7" in capsys.readouterr().err


def test_helper_refuses_a_handoff_without_uv_arguments(monkeypatch, capsys) -> None:
    """Refuse to run uv at all when the handoff does not name a command."""
    monkeypatch.setattr(helper.sys, "argv", ["_tool_helper", "1", "token", "uv"])

    assert helper.main() == 1
    assert "invalid deferred uv handoff" in capsys.readouterr().err
