"""Offline tests for opaque pid/create-time/executable-file GPU identities."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import bora_workbench._gpu_process_identity as identity_module
from bora_workbench._gpu_process_identity import identify_gpu_process


class _Process:
    """Expose deterministic psutil process lifecycle and executable facts."""

    def __init__(self, pid: int) -> None:
        """Retain the PID so separate instances receive separate create times."""
        self.pid = pid

    def create_time(self) -> float:
        """Return one positive instance timestamp."""
        return float(self.pid)

    def exe(self) -> str:
        """Return an unpersisted fake path whose stat identity drives matching."""
        return "C:/Program Files/Test/app.exe"


def test_same_executable_file_keeps_identity_across_process_instances(monkeypatch) -> None:
    """Match respawns by file identity while retaining distinct pid/create-time instances."""
    monkeypatch.setattr(identity_module.psutil, "Process", _Process)
    monkeypatch.setattr(
        identity_module.os, "stat", lambda path: SimpleNamespace(st_dev=7, st_ino=11)
    )

    first = identify_gpu_process(100)
    replacement = identify_gpu_process(200)

    assert first.executable_id == replacement.executable_id
    assert first.instance != replacement.instance
    assert first.is_complete and replacement.is_complete


@pytest.mark.parametrize("failure", ["process", "stat", "create-time"])
def test_identity_resolution_fails_closed(monkeypatch, failure: str) -> None:
    """Return an incomplete identity for inaccessible, vanished, or malformed process facts."""
    if failure == "process":
        monkeypatch.setattr(
            identity_module.psutil,
            "Process",
            lambda pid: (_ for _ in ()).throw(identity_module.psutil.AccessDenied(pid)),
        )
    else:
        process = _Process(100)
        if failure == "create-time":
            monkeypatch.setattr(process, "create_time", lambda: 0.0)
        monkeypatch.setattr(identity_module.psutil, "Process", lambda pid: process)
        if failure == "stat":
            monkeypatch.setattr(
                identity_module.os,
                "stat",
                lambda path: (_ for _ in ()).throw(OSError("blocked")),
            )

    assert not identify_gpu_process(100).is_complete
