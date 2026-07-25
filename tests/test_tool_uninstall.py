"""Test exact uv tool identification and helper error mapping without host removal."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import bora_workbench._tool_uninstall as tool_uninstall
import bora_workbench._tool_uninstall_helper as helper


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
    monkeypatch.setattr(tool_uninstall.sys, "prefix", str(environment))
    monkeypatch.setattr(tool_uninstall.shutil, "which", lambda _name: str(uv_executable))
    monkeypatch.setattr(tool_uninstall, "_query_tool_root", lambda _uv: tmp_path / "tools")

    installation = tool_uninstall.inspect_tool_installation()

    assert installation.environment == environment.resolve()
    assert installation.uv_executable == uv_executable.resolve()
    assert installation.is_managed_by_uv


def test_inspection_rejects_a_different_python_environment(tmp_path, monkeypatch) -> None:
    """Never remove a global uv tool merely because uninstall ran from a checkout or other venv."""
    _tool_environment(tmp_path)
    monkeypatch.setattr(tool_uninstall.sys, "prefix", str(tmp_path / "checkout" / ".venv"))
    monkeypatch.setattr(tool_uninstall.shutil, "which", lambda _name: str(tmp_path / "uv"))
    monkeypatch.setattr(tool_uninstall, "_query_tool_root", lambda _uv: tmp_path / "tools")

    installation = tool_uninstall.inspect_tool_installation()

    assert not installation.is_managed_by_uv


def test_uv_tool_directory_failure_is_actionable(monkeypatch) -> None:
    """Expose uv inspection stderr instead of guessing a tool root or deleting anything."""
    failed = SimpleNamespace(returncode=2, stdout="", stderr="invalid uv config")
    monkeypatch.setattr(tool_uninstall.subprocess, "run", lambda *args, **kwargs: failed)

    with pytest.raises(tool_uninstall.ToolUninstallError, match="invalid uv config"):
        tool_uninstall._query_tool_root(Path("uv"))


def test_handoff_token_accepts_fragmented_socket_reads() -> None:
    """Reassemble a stream token because one recv call is not guaranteed to return every byte."""
    channel = SimpleNamespace(recv=Mock(side_effect=[b"ab", b"c", b"def"]))

    assert tool_uninstall._receive_token(channel, 6) == b"abcdef"


def test_helper_reports_uv_failure(monkeypatch, capsys) -> None:
    """Keep a deferred uv failure visible even though the original command already exited."""
    failed = SimpleNamespace(returncode=7)
    monkeypatch.setattr(helper.subprocess, "run", lambda *args, **kwargs: failed)

    assert helper._run_uv("uv") == 7
    assert "exited with code 7" in capsys.readouterr().err
